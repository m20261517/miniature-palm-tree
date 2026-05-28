import requests
import pandas as pd
import streamlit as st
import datetime
import urllib.parse

# ==========================================
# 1. API 키 설정 및 디코딩
# ==========================================
SERVICE_KEY = "12843209762a114e91bf146bb7787cf097c0a7d77e477d66d521e2f9d17b2263"
DECODED_KEY = urllib.parse.unquote(SERVICE_KEY)

# 경기도 주요 시/군 행정표준코드 및 기상청 격자 좌표(nx, ny)
LOCATIONS = {
    "수원시": (60, 121), "성남시": (62, 123), "고양시": (57, 128),
    "용인시": (62, 120), "부천시": (56, 125), "안산시": (58, 121),
    "안양시": (59, 123), "남양주시": (64, 128), "화성시": (57, 119),
    "평택시": (61, 114), "의정부시": (61, 130), "시흥시": (57, 123),
    "파주시": (56, 131), "김포시": (55, 128), "광명시": (58, 125),
    "광주시": (65, 123), "군포시": (59, 122), "오산시": (62, 118),
    "이천시": (68, 119), "양주시": (61, 131), "안성시": (65, 115),
    "구리시": (62, 127), "포천시": (64, 134), "의왕시": (60, 122),
    "하남시": (64, 126), "여주시": (71, 121), "동두천시": (61, 134),
    "과천시": (60, 124), "가평군": (69, 133), "양평군": (69, 125),
    "연천군": (58, 138)
}

# ==========================================
# 2. 기상청 최근 발표 시각 자동 계산 함수 (에러 방지 핵심)
# ==========================================
def get_recent_base_datetime():
    # KST 기준 현재 시간 (서버 배포 시 시간대 오류 방지)
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    # 기상청 업데이트 지연을 고려해 현재 시간에서 15분을 뺌
    now -= datetime.timedelta(minutes=15)
    
    hour = now.hour
    if hour < 2:
        base_date = (now - datetime.timedelta(days=1)).strftime("%Y%m%d")
        base_time = "2300"
    else:
        base_date = now.strftime("%Y%m%d")
        # 02, 05, 08, 11, 14, 17, 20, 23시 중 가장 최근 시간 계산
        base_hour = (hour + 1) // 3 * 3 - 1
        base_time = f"{base_hour:02d}00"
        
    return base_date, base_time

# ==========================================
# 3. 데이터 수집 함수
# ==========================================
@st.cache_data(ttl=1800) # 30분 단위 캐싱으로 API 호출 속도 최적화
def fetch_weather(target_date_str, nx, ny, target_hours=["12","13"]):
    base_date, base_time = get_recent_base_datetime()
    url = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
    
    params = {
        "serviceKey": DECODED_KEY,
        "numOfRows": "500",  # 오늘~모레까지 데이터를 충분히 가져옴
        "pageNo": "1",
        "dataType": "JSON",
        "base_date": base_date,
        "base_time": base_time,
        "nx": nx,
        "ny": ny
    }
    
    TMPs, POPs = {h: None for h in target_hours}, {h: None for h in target_hours}
    
    try:
        res = requests.get(url, params=params, timeout=5)
        data = res.json()
        
        # 기상청 API 정상 응답 여부 확인
        if data["response"]["header"]["resultCode"] != "00":
            return TMPs, POPs
            
        items = data["response"]["body"]["items"]["item"]
        
        for item in items:
            # 예보 대상일(fcstDate)이 우리가 알고 싶은 날짜와 같을 때만 데이터 추출
            if item["fcstDate"] == target_date_str:
                fcst_hour = item["fcstTime"][:2]
                if fcst_hour in target_hours:
                    if item["category"] == "TMP":
                        TMPs[fcst_hour] = float(item["fcstValue"])
                    elif item["category"] == "POP":
                        POPs[fcst_hour] = float(item["fcstValue"])
                        
        return TMPs, POPs
        
    except Exception:
        return TMPs, POPs

# ==========================================
# 4. 점심시간 장소 추천 우선순위 로직
# ==========================================
def judge_lunch(tmp_dict, pop_dict):
    temps = [tmp_dict.get(h) for h in ["12", "13"] if tmp_dict.get(h) is not None]
    pops = [pop_dict.get(h) for h in ["12", "13"] if pop_dict.get(h) is not None]
    
    if not temps or not pops:
        return "알 수 없음", "unknown", "해당 날짜의 예보가 아직 발표되지 않았어요. (기상청 단기예보는 최대 3일까지만 제공됩니다)"
        
    avg_temp = sum(temps) / len(temps)
    
    # 1순위 (교실): 너무 춥거나(<12도) 너무 더우면(>30도)
    if avg_temp < 12 or avg_temp > 30:
        if avg_temp < 12:
            return "교실", "classroom", f"기온이 **{avg_temp:.1f}°C**로 쌀쌀해서 실내가 안전해요."
        else:
            return "교실", "classroom", f"기온이 **{avg_temp:.1f}°C**로 너무 더워서 실내가 안전해요."
            
    # 2순위 (필로티): 기온은 적절하나, 비 소식(강수확률 30% 이상)
    max_pop = max(pops)
    if max_pop >= 30:
        return "필로티", "piloti", f"비가 올 확률이 **{max_pop}%** 있어서 비를 피할 수 있는 곳이 좋아요."
        
    # 3순위 (운동장): 기온 적절(12~30도)하고 강수확률도 낮을 때(30% 미만)
    return "운동장", "playground", "기온과 날씨 모두 야외 활동하기에 아주 완벽해요!"

def calc_lunch_summary(tmp_dict, pop_dict):
    temps = [t for t in [tmp_dict.get('12'), tmp_dict.get('13')] if t is not None]
    pops = [p for p in [pop_dict.get('12'), pop_dict.get('13')] if p is not None]
    temp_avg = round(sum(temps)/len(temps), 1) if temps else None
    pop_max = max(pops) if pops else None
    return temp_avg, pop_max

# ==========================================
# 5. Streamlit UI 구성
# ==========================================
st.set_page_config(page_title="점심시간에 나가도 돼요?", page_icon="🌤", layout="wide")

st.title("🌤 점심시간에 나가도 돼요?")
st.caption("기온과 강수확률을 바탕으로 안전한 점심시간 놀이 장소를 추천해 드립니다.")

tab1, tab2 = st.tabs(["📍 지역 선택", "📅 평일 점심시간 장소 추천"])

# --- 탭 1: 지역 선택 ---
with tab1:
    location_name = st.selectbox("경기도 내 지역을 선택하세요", list(LOCATIONS.keys()))
    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    week_dates = [monday + datetime.timedelta(days=i) for i in range(5)]
    
    st.write(f"**이번 주 평일:** {week_dates[0].strftime('%Y-%m-%d')} ~ {week_dates[-1].strftime('%Y-%m-%d')}")
    st.session_state["location_name"] = location_name
    st.session_state["week_dates"] = week_dates

# --- 탭 2: 결과 확인 및 날짜별 알림 ---
with tab2:
    if "location_name" in st.session_state and "week_dates" in st.session_state:
        location_name = st.session_state["location_name"]
        week_dates = st.session_state["week_dates"]
        nx, ny = LOCATIONS[location_name]
        
        results = []
        
        with st.spinner(f"기상청에서 {location_name} 예보를 가져오는 중입니다..."):
            for d in week_dates:
                target_date_str = d.strftime("%Y%m%d")
                tmp_dict, pop_dict = fetch_weather(target_date_str, nx, ny, target_hours=["12","13"])
                
                temp_avg, pop_max = calc_lunch_summary(tmp_dict, pop_dict)
                place, status_code, reason_str = judge_lunch(tmp_dict, pop_dict)
                
                # 내부 로직 처리를 위해 status_code, reason_str 별도 저장
                results.append({
                    "날짜": d.strftime("%Y-%m-%d"),
                    "요일": "월화수목금"[d.weekday()],
                    "기온(°C)": temp_avg if temp_avg is not None else "-",
                    "강수확률(%)": pop_max if pop_max is not None else "-",
                    "추천 장소": place,
                    "판정 이유": reason_str,
                    "_status_code": status_code, # UI 표에는 보이지 않게 숨김 처리용
                    "_reason": reason_str
                })
                    
        # 주간 예보 표 렌더링 (숨김 컬럼 제외)
        df = pd.DataFrame(results)
        display_df = df.drop(columns=["_status_code", "_reason"])
        st.dataframe(display_df, use_container_width=True, hide_index=True)
            
        st.markdown("---")
        
        # ==========================================
        # ★ 하단 알림 및 추천활동/안전수칙 UI (날짜 선택형) ★
        # ==========================================
        date_options = [r["날짜"] for r in results]
        
        # 날짜를 클릭(선택)할 수 있는 라디오 버튼 (가로 정렬로 버튼처럼 보이게 구성)
        selected_date = st.radio(
            "👇 점심시간 활동 안내를 확인할 날짜를 누르세요:", 
            date_options, 
            horizontal=True
        )
        
        # 선택된 날짜의 데이터 추출
        selected_data = next(r for r in results if r["날짜"] == selected_date)
        sel_status_code = selected_data["_status_code"]
        sel_reason = selected_data["_reason"]
        sel_weekday = selected_data["요일"]

        st.subheader(f"📢 {selected_date}({sel_weekday}) 점심시간 활동 안내")
        
        if sel_status_code == "unknown":
            st.info("아직 날씨예보가 발표되지 않았어요. (기상청 단기예보는 최대 3일까지만 제공됩니다)")
            
        elif sel_status_code == "playground":
            st.success(f"## 🏃 야외활동 최고! {sel_weekday}요일엔 [ 운동장 ] 으로 나가요!")
            st.write(f"**이유:** {sel_reason}")
            
            act_tab, safe_tab = st.tabs(["💡 추천 놀이", "🚨 안전 수칙"])
            with act_tab:
                st.write("버튼을 누르면 놀이 방법을 볼 수 있어요!")
                c1, c2, c3 = st.columns(3)
                with c1: 
                    with st.popover("⚽ 축구 / 발야구", use_container_width=True):
                        st.markdown("**축구 / 발야구 놀이방법**\n\n- 공을 발로 차서 상대편 골대에 넣거나 베이스를 돌아서 점수를 내는 활동입니다. \n- 팀을 나누어 협동심을 기를 수 있어요!")
                with c2:
                    with st.popover("🛝 놀이터 이용", use_container_width=True):
                        st.markdown("**놀이터 이용방법**\n\n- 미끄럼틀, 그네, 시소 등 기구를 번갈아가며 이용해요.\n- 차례를 지켜서 안전하게 노는 것이 규칙입니다!")
                with c3:
                    with st.popover("🏃 술래잡기", use_container_width=True):
                        st.markdown("**술래잡기 놀이방법**\n\n- 술래 한 명을 정하고, 나머지 친구들은 도망갑니다.\n- 술래에게 터치된 사람이 다음 술래가 됩니다!")
                        
            with safe_tab:
                st.info("✔ 햇빛이 뜨거울 땐 모자를 쓰고 물을 자주 마셔요!\n\n✔ 기온이 12도 정도로 약간 서늘할 수 있으니 겉옷을 꼭 챙겨 입어요.\n\n✔ 놀이기구에서 친구를 밀거나 당기지 않도록 주의해요!")
            
        elif sel_status_code == "piloti":
            st.warning(f"## ☂ 비 소식이 있어요. {sel_weekday}요일엔 [ 필로티 ] 에서 놀아요!")
            st.write(f"**이유:** {sel_reason}")
            
            act_tab, safe_tab = st.tabs(["💡 추천 놀이", "🚨 안전 수칙"])
            with act_tab:
                st.write("버튼을 누르면 놀이 방법을 볼 수 있어요!")
                c1, c2, c3 = st.columns(3)
                with c1: 
                    with st.popover("🏐 피구", use_container_width=True):
                        st.markdown("**피구 놀이방법**\n\n- 공을 던져 상대편을 맞추는 게임입니다.\n- 공에 맞으면 아웃되어 경기장 추방 밖으로 나가야 해요.")
                with c2: 
                    with st.popover("🪢 단체 줄넘기", use_container_width=True):
                        st.markdown("**단체 줄넘기 놀이방법**\n\n- 두 사람이 긴 줄을 돌리고, 나머지 친구들이 타이밍을 맞춰 줄 안으로 들어가 뜁니다.")
                with c3: 
                    with st.popover("🪙 수건돌리기", use_container_width=True):
                        st.markdown("**수건돌리기 놀이방법**\n\n- 둥글게 앉아 눈을 감고, 술래가 몰래 수건을 친구 등 뒤에 놓습니다.\n- 눈치를 챈 친구는 일어나서 술래를 잡아야 해요!")
                        
            with safe_tab:
                st.warning("✔ 비가 내려 바닥이 미끄러울 수 있으니 절대 뛰지 않아요!\n\n✔ 기둥에 부딪히지 않도록 활동 범위를 정해놓고 놀아요!")
            
        elif sel_status_code == "classroom":
            st.error(f"## 🌡 안전을 위해 {sel_weekday}요일엔 [ 교실 ] 에서 놀아요!")
            st.write(f"**이유:** {sel_reason}")
            
            act_tab, safe_tab = st.tabs(["💡 추천 놀이", "🚨 안전 수칙"])
            with act_tab:
                st.write("버튼을 누르면 놀이 방법을 볼 수 있어요!")
                c1, c2, c3 = st.columns(3)
                with c1: 
                    with st.popover("🎲 보드게임", use_container_width=True):
                        st.markdown("**보드게임 놀이방법**\n\n- 교실에 있는 보드게임 규칙서를 읽고 정해진 룰에 따라 조별로 게임을 진행해요.")
                with c2: 
                    with st.popover("⚪ 공기놀이", use_container_width=True):
                        st.markdown("**공기놀이 놀이방법**\n\n- 공기알 5개를 이용해 1단부터 5단 꺾기까지 진행하며 점수를 내는 놀이입니다.")
                with c3: 
                    with st.popover("🔍 교실 보물찾기", use_container_width=True):
                        st.markdown("**교실 보물찾기 놀이방법**\n\n- 선생님이나 술래가 숨겨둔 쪽지(보물)를 교실 안에서 훼손 없이 찾아내는 놀이입니다.")
                        
            with safe_tab:
                st.error("✔ 교실 안에서는 절대 뛰거나 공을 던지지 않아요!\n\n✔ 책상이나 의자 모서리에 부딪혀 다칠 수 있으니 조심해요!")
