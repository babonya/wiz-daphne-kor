v18.09 개선 핵심: 알파벳/숫자 순 정렬 (sorted()) 지원
파일 로딩 시 sorted(glob.glob(pattern))를 적용하여 파일명 오름차순으로 템플릿을 탐색하도록 정밀 제어했습니다.
이제 유저분께서 파일명 맨 앞에 번호를 붙여 우선순위를 완벽하게 제어할 수 있습니다.
힐러 설정 예시:
templates/healer_1_ekaterina.png (가장 먼저 화면 매칭 수행 ➔ 1순위)
templates/healer_2_alice.png (예카테리나가 화면에 없거나 매칭 실패 시 수행 ➔ 2순위)
따개 설정 예시 (동일 적용):
templates/disarmer_1_milana.png (해제 선택창에서 우선 선택 ➔ 1순위)
templates/disarmer_2_other.png (2순위)