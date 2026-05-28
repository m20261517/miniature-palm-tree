import requests
import pandas as pd
import streamlit as st
import datetime
import urllib.parse
import time

# ==========================================
# 1. API 키 설정 및 디코딩
# ==========================================
SERVICE_KEY = "12843209762a114e91bf146bb7787cf097c0a7d77e477d66d521e2f9d17b2263"
DECODED_KEY = urllib.parse.unquote(SERVICE_KEY)

# 경기도 31개 시·군 기상청 격자 좌표(nx, ny)
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

WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]
REL_LABEL = {0: "오늘", 1: "내일", 2: "모레"}

# ==========================================
# 2. 시간 계산 (전부 KST 기준 — 서버가 UTC라도 안전)
# ==========================================
KST = datetime.timezone(datetime.timedelta(hours=9))

def kst_now():
    # Streamlit Cloud 서버는 UTC라서 한국시간(KST)으로 변환
    return datetime.datetime.now(KST)

def get_recent_base_datetime():
    # 오늘 점심(12~13시)이 오후·저녁에도 항상 예보에 포함되도록 base_time을 1100 이하로 제한한다.
    # (1400 이후 발표는 예보가 14시부터 시작해 오늘 점심이 빠져버림)
    now = kst_now() - datetime.timedelta(minutes=15)  # 기상청 제공 지연 버퍼
    if now.hour < 2:
        # 새벽엔 전날 2300 발표 사용 (오늘 0시 이후 예보 포함)
        base_date = (now - datetime.timedelta(days=1)).strftime("%Y%m%d")
        return base_date, "2300"
    # 02,05,08,11 발표 중 지금까지 나온 가장 최근 시각 (11시 상한 → 오늘 점심 포함)
    base_date = now.strftime("%Y%m%d")
    for bt in (11, 8, 5, 2):
        if now.hour >= bt:
            return base_date, f"{bt:02d}00"
    return base_date, "0200"

# ==========================================
# 3. 데이터 수집 (단기예보 — 한 번 호출로 오늘~모레 전부 받음)
# ==========================================
# 성공한 결과만 30분 캐싱한다. 실패하면 예외를 던져서 캐시되지 않게 하고
# (st.cache_data는 예외를 캐시하지 않음), 다음 실행 때 다시 시도하도록 한다.
@st.cache_data(ttl=1800)
def fetch_weather(nx, ny):
    base_date, base_time = get_recent_base_datetime()
    url = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
    params = {
        "serviceKey": DECODED_KEY,
        "numOfRows": "1000",  # 오늘~모레 12~13시까지 잘리지 않게 충분히 받음
        "pageNo": "1",
        "dataType": "JSON",
        "base_date": base_date,
        "base_time": base_time,
        "nx": nx,
        "ny": ny,
    }

    last_err = "알 수 없는 오류"
    for _ in range(3):  # 일시적 실패(네트워크/혼잡)에 대비해 최대 3회 재시도
        try:
            res = requests.get(url, params=params, timeout=8)
            if res.status_code != 200:
                last_err = f"HTTP {res.status_code}"
                time.sleep(0.6)
                continue
            data = res.json()
            if data["response"]["header"]["resultCode"] != "00":
                last_err = data["response"]["header"].get("resultMsg", "API 오류")
                time.sleep(0.6)
                continue

            items = data["response"]["body"]["items"]["item"]
            # 날짜별 {"TMP": {시각: 값}, "POP": {시각: 값}} 형태로 정리
            by_date = {}
            for item in items:
                d = item["fcstDate"]
                cat = item["category"]
                if cat not in ("TMP", "POP"):
                    continue
                by_date.setdefault(d, {"TMP": {}, "POP": {}})
                by_date[d][cat][item["fcstTime"][:2]] = float(item["fcstValue"])
            return by_date
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            time.sleep(0.6)

    raise RuntimeError(last_err)


def extract_day(by_date, date_str, hours=("12", "13")):
    day = by_date.get(date_str, {"TMP": {}, "POP": {}})
    tmp = {h: day["TMP"].get(h) for h in hours}
    pop = {h: day["POP"].get(h) for h in hours}
    return tmp, pop

# ==========================================
# 4. 장소 추천 우선순위 로직 (운동장 > 필로티 > 교실)
# ==========================================
def judge_lunch(tmp_dict, pop_dict):
    temps = [v for v in tmp_dict.values() if v is not None]
    pops = [v for v in pop_dict.values() if v is not None]

    if not temps or not pops:
        return "알 수 없음", "unknown", "점심 예보가 아직 없거나 이미 지난 시간이에요. (단기예보는 오늘~모레까지 제공돼요)"

    avg_temp = sum(temps) / len(temps)

    # 기온이 범위를 벗어나면 교실 (최우선 안전 판단)
    if avg_temp < 12:
        return "교실", "classroom", f"기온이 {avg_temp:.1f}°C로 쌀쌀해서 실내가 안전해요."
    if avg_temp > 30:
        return "교실", "classroom", f"기온이 {avg_temp:.1f}°C로 너무 더워서 실내가 안전해요."

    # 기온은 적절하지만 비 소식 → 필로티
    max_pop = max(pops)
    if max_pop >= 30:
        return "필로티", "piloti", f"기온은 좋지만 비 올 확률이 {max_pop:.0f}%라 비를 피할 수 있는 곳이 좋아요."

    # 기온 적절 + 비 안 옴 → 운동장
    return "운동장", "playground", f"기온 {avg_temp:.1f}°C, 강수확률 {max_pop:.0f}%로 야외활동에 딱 좋아요!"

def calc_summary(tmp_dict, pop_dict):
    temps = [v for v in tmp_dict.values() if v is not None]
    pops = [v for v in pop_dict.values() if v is not None]
    temp_avg = round(sum(temps) / len(temps), 1) if temps else None
    pop_max = max(pops) if pops else None
    return temp_avg, pop_max

# ==========================================
# 5. 장소별 추천 놀이 & 안전수칙 데이터
# ==========================================
PLACE_INFO = {
    "playground": {
        "box": "success",
        "headline": "🏃 야외활동 최고! [ 운동장 ] 으로 나가요!",
        "activities": [
            ("⚽ 축구 / 발야구", "**축구 / 발야구 놀이방법**\n\n- 공을 발로 차서 상대편 골대에 넣거나 베이스를 돌아 점수를 냅니다.\n- 팀을 나누어 협동심을 길러요!"),
            ("🛝 놀이터 이용", "**놀이터 이용방법**\n\n- 미끄럼틀, 그네, 시소 등을 번갈아가며 이용해요.\n- 차례를 지켜서 안전하게 노는 것이 규칙입니다!"),
            ("🏃 술래잡기", "**술래잡기 놀이방법**\n\n- 술래 한 명을 정하고 나머지 친구들은 도망갑니다.\n- 술래에게 터치된 사람이 다음 술래가 돼요!"),
        ],
        "safety_box": "info",
        "safety": "✔ 햇빛이 뜨거울 땐 모자를 쓰고 물을 자주 마셔요!\n\n✔ 기온이 12도 정도면 약간 서늘할 수 있으니 겉옷을 챙겨요.\n\n✔ 놀이기구에서 친구를 밀거나 당기지 않아요!",
    },
    "piloti": {
        "box": "warning",
        "headline": "☂ 비 소식이 있어요. [ 필로티 ] 에서 놀아요!",
        "activities": [
            ("🏐 피구", "**피구 놀이방법**\n\n- 공을 던져 상대편을 맞히는 게임입니다.\n- 공에 맞으면 아웃되어 경기장 밖으로 나가요."),
            ("🪢 단체 줄넘기", "**단체 줄넘기 놀이방법**\n\n- 두 사람이 긴 줄을 돌리고, 나머지 친구들이 타이밍을 맞춰 줄 안으로 들어가 뜁니다."),
            ("🪙 수건돌리기", "**수건돌리기 놀이방법**\n\n- 둥글게 앉아 눈을 감고, 술래가 몰래 수건을 친구 등 뒤에 놓습니다.\n- 눈치챈 친구는 일어나 술래를 잡아요!"),
        ],
        "safety_box": "warning",
        "safety": "✔ 비가 내려 바닥이 미끄러울 수 있으니 절대 뛰지 않아요!\n\n✔ 기둥에 부딪히지 않도록 활동 범위를 정해놓고 놀아요!",
    },
    "classroom": {
        "box": "error",
        "headline": "🌡 안전을 위해 [ 교실 ] 에서 놀아요!",
        "activities": [
            ("🎲 보드게임", "**보드게임 놀이방법**\n\n- 보드게임 규칙서를 읽고 정해진 룰에 따라 조별로 게임을 진행해요."),
            ("⚪ 공기놀이", "**공기놀이 놀이방법**\n\n- 공기알 5개로 1단부터 5단 꺾기까지 진행하며 점수를 냅니다."),
            ("🔍 교실 보물찾기", "**교실 보물찾기 놀이방법**\n\n- 술래가 숨겨둔 쪽지(보물)를 교실 안에서 훼손 없이 찾아내는 놀이입니다."),
        ],
        "safety_box": "error",
        "safety": "✔ 교실 안에서는 절대 뛰거나 공을 던지지 않아요!\n\n✔ 책상·의자 모서리에 부딪혀 다칠 수 있으니 조심해요!",
    },
}

def render_box(kind, text):
    {"success": st.success, "warning": st.warning, "error": st.error, "info": st.info}[kind](text)

def render_place(status_code, reason):
    info = PLACE_INFO[status_code]
    render_box(info["box"], info["headline"])
    st.caption(f"💬 {reason}")

    act_tab, safe_tab = st.tabs(["💡 추천 놀이", "🚨 안전 수칙"])
    with act_tab:
        st.write("버튼을 누르면 놀이 방법을 볼 수 있어요!")
        cols = st.columns(len(info["activities"]))
        for col, (title, how) in zip(cols, info["activities"]):
            with col:
                with st.popover(title, use_container_width=True):
                    st.markdown(how)
    with safe_tab:
        render_box(info["safety_box"], info["safety"])

# ==========================================
# 6. Streamlit UI
# ==========================================
st.set_page_config(page_title="점심시간에 나가도 돼요?", page_icon="🌤", layout="wide")

st.title("🌤 점심시간에 나가도 돼요?")
st.caption("기온과 강수확률을 바탕으로 안전한 점심시간 놀이 장소를 추천해 드려요. (오늘~모레 예보)")

tab1, tab2 = st.tabs(["📍 지역 선택", "📅 점심시간 장소 추천"])

# --- 탭 1: 지역 선택 ---
with tab1:
    location_name = st.selectbox("경기도 내 지역을 선택하세요", list(LOCATIONS.keys()))
    st.session_state["location_name"] = location_name
    st.info("지역을 고른 뒤 위의 '📅 점심시간 장소 추천' 탭을 눌러 결과를 확인하세요!")

# --- 탭 2: 결과 ---
with tab2:
    location_name = st.session_state.get("location_name", list(LOCATIONS.keys())[0])
    nx, ny = LOCATIONS[location_name]
    today = kst_now().date()
    day_list = [today + datetime.timedelta(days=i) for i in range(3)]  # 오늘, 내일, 모레

    st.markdown(f"#### 📍 {location_name} · 점심시간(12~13시) 예보")

    by_date = None
    fetch_error = None
    with st.spinner(f"기상청에서 {location_name} 예보를 가져오는 중입니다..."):
        try:
            by_date = fetch_weather(nx, ny)  # 한 번 호출로 오늘~모레 전부
        except Exception as e:
            fetch_error = str(e)

    if fetch_error:
        st.error("기상청 서버에서 예보를 받지 못했어요. 잠시 후 다시 시도해 주세요.")
        st.caption(f"(원인: {fetch_error})")
        if st.button("🔄 다시 시도"):
            fetch_weather.clear()  # 캐시 비우고 다시 호출
            st.rerun()
        st.stop()

    results = []
    for offset, d in enumerate(day_list):
        tmp_dict, pop_dict = extract_day(by_date, d.strftime("%Y%m%d"))
        temp_avg, pop_max = calc_summary(tmp_dict, pop_dict)
        place, status_code, reason = judge_lunch(tmp_dict, pop_dict)
        results.append({
            "구분": REL_LABEL[offset],
            "날짜": d.strftime("%m/%d") + f" ({WEEKDAY_KR[d.weekday()]})",
            "기온(°C)": temp_avg if temp_avg is not None else "-",
            "강수확률(%)": pop_max if pop_max is not None else "-",
            "추천 장소": place,
            "_status_code": status_code,
            "_reason": reason,
        })

    df = pd.DataFrame(results)
    st.dataframe(
        df.drop(columns=["_status_code", "_reason"]),
        use_container_width=True, hide_index=True,
    )

    st.markdown("---")

    # 날짜 선택 → 활동/안전수칙 안내
    option_labels = [f"{r['구분']} ({r['날짜']})" for r in results]
    selected_label = st.radio("👇 안내를 확인할 날짜를 누르세요:", option_labels, horizontal=True)
    selected = results[option_labels.index(selected_label)]

    st.subheader(f"📢 {selected['구분']}({selected['날짜']}) 점심시간 활동 안내")

    if selected["_status_code"] == "unknown":
        st.info(selected["_reason"])
    else:
        render_place(selected["_status_code"], selected["_reason"])
