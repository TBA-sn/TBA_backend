# TBA_backend

## 🧱 1️⃣ 프로젝트 클론 및 가상환경 설정


git clone https://github.com/TBA-sn/TBA_backend

cd TBA_backend

python3 -m venv .venv

source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -U pip

pip install -r requirements.txt


루트 폴더 안에 env
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=tba_db
DB_USER=root
DB_PASSWORD=000000

GITHUB_REDIRECT=http://localhost:8000/auth/github/callback

JWT_SECRET=dev-secret
JWT_ALG=HS256

db 이름은 알아서.. 비번이랑..

mysql에 접속 
그런데 저는 datagrip이 편해서 쓴건데 
<img width="799" height="677" alt="image" src="https://github.com/user-attachments/assets/9bcd71de-3ac4-42fd-890f-56304df9bb56" />


이렇게 설정해서 비번만 치면 되는데 음..
use tba_db하고
1. 데이터베이스 테이블 다 drop
2. 파이썬 /migration/14e~~.py   이런 파일들 다 삭제
2. 파이썬 실행
3. 명령어 치기…
   alembic revision --autogenerate -m "init tables"    # 원하는 거 암거나
   alembic upgrade head
4. 데이터베이스 새로고침 해보면 테이블 만들어져있을 거임…

서버 실행
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

localhost:8000 들어가면 ui 뜹니다!

curl "http://localhost:8000/auth/github/debug/mint?user_id=원하는 id“
Api 테스트에 넣어야함
Authorization 옵션 (토큰 직접 입력) 누르고 토큰 나온거 복붙하고 엔터 그럼 밑에 알아서
<img width="683" height="862" alt="스크린샷 2025-11-07 오후 5 34 27" src="https://github.com/user-attachments/assets/49222f98-bc1c-4271-a408-3be857567de4" />




이런식으로 쭉 뜰겁니다!


