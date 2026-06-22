"""GMP validation default workflow template tests."""

from agent.workflow.storage import load_template


def test_gmp_validation_template_has_quality_evaluation_steps(vault):
    template = load_template("gmp-validation")
    titles = [step["title"] for step in template["steps"]]

    assert template["title"] == "GMP 기능명세 검증 절차"
    assert titles == [
        "초기 질문 및 평가 범위 확정",
        "SharePoint/로컬 문서 확보 및 artifact 기록",
        "Excel/CSV 기능명세 요구사항 목록 추출",
        "Obsidian·코드·사내 웹 증거 수집",
        "Requirement coverage matrix 작성",
        "불일치·미확인 항목 승인 포인트 확인",
        "결과 보고 및 Obsidian 지식화",
    ]
    assert template["steps"][1]["type"] == "semi_auto"
    assert template["steps"][5]["type"] == "manual"
