import sys
import json
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

print("=== 1. JWT 발급 (/jwt-auth/login) 테스트 ===")
res1 = client.post("/jwt-auth/login", json={"user_id": "test-user-1234"})
print("Status:", res1.status_code)
print("Response:", json.dumps(res1.json(), indent=2, ensure_ascii=False))

if res1.status_code == 200:
    data = res1.json()["data"]
    access_token = data["access_token"]
    refresh_token = data["refresh_token"]

    print("\n=== 2. JWT 검증 및 로그아웃 (/jwt-auth/logout) 테스트 ===")
    res2 = client.put(
        "/jwt-auth/logout",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    print("Status:", res2.status_code)
    print("Response:", json.dumps(res2.json(), indent=2, ensure_ascii=False))

    print("\n=== 3. JWT 갱신 (/jwt-auth/refresh) 테스트 ===")
    res3 = client.post(
        "/jwt-auth/refresh",
        json={"refresh_token": refresh_token}
    )
    print("Status:", res3.status_code)
    print("Response:", json.dumps(res3.json(), indent=2, ensure_ascii=False))

    print("\n=== 4. 에러 테스트 (유효하지 않은 토큰) ===")
    res4 = client.put(
        "/jwt-auth/logout",
        headers={"Authorization": "Bearer iam_fake_token_123"}
    )
    print("Status:", res4.status_code)
    print("Response:", json.dumps(res4.json(), indent=2, ensure_ascii=False))
