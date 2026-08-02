# 구현 계획서 (v1.17.0 후속 패치)

작성일: 2026-08-02 (2차 수정)
목적: 로그(`logs/2026-08-02-1626/1630/1839`) + 실측 템플릿 매칭 테스트로 확인된, 실제로 매크로를 멈추게 하는 문제들을 수정합니다.

---

## 항목 1. `t_open_world`("세계지도를 연다") 그레이스케일 로딩 전환

**현재 문제**
`src/main.py`에서 `t_open_world = load_template("templates/open_world_map_btn.png")`로 로드됩니다.
`load_template`은 이진화(임계값 160) 방식인데, 실측 결과 이 방식이 던전마다 들쭉날쭉합니다:

| 던전 | 그레이스케일 | 이진화(160) |
|---|---|---|
| 백아의늑대동굴 | 1.000 | 0.992 |
| 꽃의동굴 | 0.957 | **0.591** |
| 치유사의마을유적 | 0.978 | 0.926 |
| 고대영묘 | 0.966 | 0.705 |
| 유령성 | 0.958 | **0.628** |

실제 로그(`1626`/`1630`/`1839`)에서 유령성 던전선택창을 빠져나가지 못하고
ESC 폴백 → 세계지도 오판정(0.80 < 0.83 임계값) → 5분 정체 → 강제 리부팅이 반복된 게 이 이진화 매칭 실패가 원인이었습니다.

**수정 내용**
- `src/main.py` 내 `t_open_world = load_template(...)` 2곳(부팅 복구용, 대순환 루프용)을 `load_grayscale_template`로 교체.
- 던전별 분기 신설 없이, 기존 공용 도장 1개를 그대로 재활용.

**리스크**: 낮음. 5개 던전 전수 테스트로 0.957 이상 확인됨.

---

## 항목 2. 던전선택 로그에 던전명 표시

**수정 내용**: `DUNGEON_SEL` 관련 print문에 기존 `DUNGEON_NAME` 변수를 삽입.

**리스크**: 없음. 로그 문자열만 수정.

---

## 항목 3. 월드맵 지그재그 탐색 Step 1 스케일 보정

**현재 문제**: `worldmap_drag_step == 1`의 스와이프 이동거리가 `(100, -100)`px로, 이웃 스텝(700~1800px) 대비 1/7~1/18 수준.

**수정 내용**: Step 1 좌표를 이웃 스텝과 비슷한 크기로 재조정. 정확한 최종값은 실행 중 육안 확인 후 미세조정 필요.

**리스크**: 낮음~중간.

---

## 항목 4. 광석파밍 회군 조건 전면 재설계 (신규, 우선순위 최상위)

**현재 문제** (`logs/2026-08-02-1839-000_start.txt`로 실증)
[main.py:1537-1539](src/main.py:1537):
```python
dungeon_run_count += 1
if FARMING_METHOD == "광석파밍":
    dungeon_run_count = LIMIT_DUNGEON_LOOPS
```
`dungeon_bot.start_main_macro()`는 "곡괭이 부족"으로 나온 경우와 "이번 채굴을 정상적으로 다 캐서" 나온 경우가
**둘 다 동일하게 `return False, skill_mission_success_this_combat`**를 반환합니다
([dungeon_bot.py:1202](src/dungeon_bot.py:1202), [1220](src/dungeon_bot.py:1220)).
그 결과 사령탑은 둘을 구분 못 하고, 광석파밍이면 **어떤 이유로 나왔든 무조건** 회군 처리를 해버립니다.

**사용자 확정 요구사항**
- 광석파밍은 상자파밍의 N주회 카운터(`dungeon_run_count`/`LIMIT_DUNGEON_LOOPS`)를 아예 타지 않고, **"곡괭이 부족" 감지 시에만** 마을 회군.
- 그 외의 경우(정상 채굴 종료)는 **무한 재진입**.
- 부가: `LIMIT_DUNGEON_LOOPS = 0`을 상자파밍에서도 "무한 주회"로 동작하도록 별도 수정 (현재는 `dungeon_run_count < 0`이 항상 거짓이라 0을 넣으면 즉시 회군해버리는 버그).

**수정 내용**
1. `dungeon_bot.start_main_macro()`가 반환값에 "곡괭이 부족으로 나왔다" 플래그를 추가로 실어 보냄 (`need_pickaxe_refill` 등, 튜플 확장).
2. `main.py`에 `need_pickaxe_refill` 상태 변수를 신설(기존 `is_fully_healed`와 동급 위치)하여, dungeon_bot이 이 플래그를 True로 반환하면 세팅.
3. `DUNGEON_SEL` 분기를 파밍 방식별로 완전히 분리:
   - `FARMING_METHOD == "광석파밍"`: `need_pickaxe_refill`이 True가 아니면 무조건 재진입(무한 루프), True면 월드맵으로 나가서 마을행. `dungeon_run_count`/`LIMIT_DUNGEON_LOOPS`는 광석파밍에서 아예 참조하지 않음.
   - 그 외(상자파밍): 기존 로직 유지 + `LIMIT_DUNGEON_LOOPS == 0`이면 카운트 검사 없이 항상 재진입하도록 조건 보강.
4. 여관 숙박 완료 시(`main.py`의 INN 처리 블록) `need_pickaxe_refill = False`로 리셋하여 다음 채굴 사이클이 정상적으로 무한 루프를 재개하도록 함.

**리스크**: 낮음. `dungeon_bot.py`의 반환 시그니처가 하나 늘어나므로, 호출부 2곳(main.py 내 `start_main_macro` 호출부) 동시 수정 필요.

---

## 항목 5. village_common 마을 상태 판별 체계로 전환

**결정된 설계**
- **"마을에 있다" 판별 앵커**: `village_common/inn.png` (그레이스케일, 임계값 0.65). 5개 마을 전수 테스트에서 가장 안정적(0.946~0.997)이었고, 어떤 마을이든 여관은 존재. 기존 마을별 개별 앵커(`Vill_Isbelg/village_anchor.png`, `FFXI/!!vill_FFXI.png` 등)는 전부 대체 → 파일 삭제로 인한 재발 위험도 근본적으로 제거됨.
- **캐릭터창 펼침 예외 처리 우선순위**: 마을 상태 처리 진입 시 `char_down.png`(이진화, 0.65)부터 먼저 확인 → 감지되면 접기 클릭 후 나머지 판별 진행. (펼쳐진 상태에서는 월드맵 아이콘이 가려지므로, 월드맵 아이콘은 앵커로 사용하지 않음 — 클릭 전용으로만 사용)
- **여관 이동**: 안 쉬었으면 `inn.png` 클릭 (기존 마을별 `village_to_inn_btn.png` 대체).
- **월드맵으로 나가기**: 다 쉬었으면 기존 고정 좌표(93%,93%) blind tap 대신 `worldmap_icon.png`(이진화, 0.80) 실제 매칭 클릭.
- **`go_outside.png`(마을외곽) 연동은 보류**: 현재 프리셋 2개(백아, 유령성)가 전부 월드맵 직행형이라 실제 테스트 대상이 없음. 마을경유형 던전을 처음 추가할 때 같이 연동.

**영향 범위**
- `src/main.py`: `recover_app_startup()` (부팅 시 마을 판별), `start_grand_orchestrator()` VILLAGE 처리 블록([main.py:1642-1661](src/main.py:1642))
- `src/inn_manager.py`: `t_village` 로딩([inn_manager.py:123](src/inn_manager.py:123)) 및 숙박 종료 조건([inn_manager.py:238](src/inn_manager.py:238))도 동일 앵커로 교체

**부수 효과**: `!!vill_FFXI.png` 삭제로 인한 노던할로우 마을 인식 불가 버그가 이 전환으로 자동 해소됨 (더 이상 마을별 파일에 의존하지 않으므로).

**리스크**: 중간. 마을 상태 판별 로직 자체를 교체하는 구조 변경이라 항목 1~4보다 범위가 큼. 다만 도장 방식/임계값은 이미 5개 마을 전수 테스트로 검증 완료.

---

## 제외 항목
- **정체 감지 모듈화(미니맵 기반 vs 커서 기반)**: 사용자님이 이미 우선순위 후순위로 미루신 항목.
- **`go_outside.png` 마을경유형 던전 연동**: 위 항목 5 참고, 첫 마을경유형 던전 추가 시점으로 연기.

---

## 적용 파일
- `src/main.py`
- `src/dungeon_bot.py`
- `src/inn_manager.py`
- `history.log`
- `Daphne Antigravity.bat` (버전 넘버가 바뀌는 경우)

이 5가지 항목으로 진행해도 될지 확인 부탁드립니다. 승인해주시면 코딩 들어가겠습니다.
