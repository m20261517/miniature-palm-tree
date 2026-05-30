# 🌤 점심시간에 나가도 돼요? (Lunchtime Weather Predictor)

[cite_start]경기도 지역의 날씨에 따라 안전한 점심시간 놀이 장소를 추천하고, 장소에 맞는 놀이와 안전수칙을 안내하는 앱입니다. [cite: 6] [cite_start]매일 점심시간마다 야외 활동을 기대하는 초등학생들을 위해, 교사가 명확한 기상 기준을 바탕으로 안전하게 장소를 안내할 수 있도록 돕습니다. [cite: 34, 73]

- [cite_start]**개발자:** 주민경 (서울교대 교육대학원 / M20261517) [cite: 6]
- [cite_start]**배포 주소:** [Streamlit App 바로가기](https://miniature-palm-tree-qbg3kafcsaynhcvp5j4usm.streamlit.app/) [cite: 6]

---

## 📂 주요 기능 명세

| 기능 구분 | 주요 내용 | 화면 결과 및 특징 |
|---|---|---|
| **기본 기능** | 지역 선택 및 날씨 조회 | [cite_start]'지역선택' 탭에서 경기도 내 도시를 선택하여 기상청 단기예보 데이터를 준비합니다. [cite: 15, 37] |
| **기본 기능** | 3일간 날씨 및 장소 추천 표 | [cite_start]'점심시간 장소 추천' 탭에서 오늘, 내일, 모레의 기상 상황이 표 형태로 표시됩니다. [cite: 17, 26] |
| **기본 기능** | 맞춤형 놀이 안내 | [cite_start]추천 장소(운동장, 필로티, 교실)에 알맞은 놀이 활동 3가지를 표시합니다. [cite: 19] |
| **심화 기능 1** | 💡 **팝오버 놀이 방법 설명** | [cite_start]개별 놀이 버튼 클릭 시, 화면 이동 없이 팝오버(Popover) 형태로 상세 놀이 규칙이 뜹니다. [cite: 22, 30] |
| **심화 기능 2** | 🚨 **상황 맞춤형 안전 수칙** | [cite_start]기온, 강수 확률, 장소 특성에 맞춰 꼭 필요한 안전수칙 2~3가지를 직관적으로 제공합니다. [cite: 24, 32] |
| **심화 기능 3** | 📊 **장소 추천 알고리즘** | [cite_start]선택한 날짜의 기온(12~30°C)과 강수확률(30% 미만)을 기준으로 교실, 필로티, 운동장의 추천 우선순위를 자동 판별하고 근거를 제시합니다.  |

---

## 🚀 어떻게 사용하나요 (설치 및 실행)

### 로컬 환경에서 실행하기
본 프로젝트를 자신의 컴퓨터에서 직접 실행해 보려면 아래의 절차를 따르세요.

```bash
# 1) 저장소 클론 (본인 폴더로 복사)
git clone [https://github.com/m20261517/miniature-palm-tree.git](https://github.com/m20261517/miniature-palm-tree.git)

# 2) 프로젝트 폴더로 이동
cd miniature-palm-tree

# 3) 가상환경 생성 및 실행 (선택 사항)
python -m venv .venv
source .venv/bin/activate  # (Windows의 경우: .venv\Scripts\activate)

# 4) 필수 라이브러리 설치
pip install requests pandas streamlit

# 5) 앱 실행
streamlit run app.py
