from langchain_core.tools import tool

@tool
def check_auth_status(user_id: str) -> str:
    """사용자의 로그인(인증) 상태를 확인합니다.
    
    사용자가 로그인 되어 있는지 물어보거나 본인의 인증 상태를 확인할 때 호출합니다.
    예: '나 로그인 되어있어?', '내 상태 확인해줘', '나 누구로 접속했어?'
    
    Args:
        user_id: JWT에서 추출한 사용자 ID. voice/router.py 가 주입합니다.
        
    Returns:
        TTS로 읽힐 자연어 문자열.
    """
    if user_id:
        return "네, 고객님은 현재 정상적으로 로그인되어 있습니다."
    return "아니요, 현재 로그아웃 상태입니다. 로그인을 먼저 진행해 주세요."

@tool
def agent_logout(user_id: str) -> str:
    """사용자를 로그아웃 처리합니다.
    
    사용자가 명시적으로 로그아웃을 요청할 때 호출합니다.
    예: '이제 그만 쓸래 로그아웃 해줘', '접속 끊어줘', '로그아웃 할래'
    
    Args:
        user_id: JWT에서 추출한 사용자 ID. voice/router.py 가 주입합니다.
        
    Returns:
        TTS로 읽힐 자연어 문자열.
    """
    return "로그아웃 처리가 완료되었습니다. 우리 톡 뱅킹을 이용해 주셔서 감사합니다."
