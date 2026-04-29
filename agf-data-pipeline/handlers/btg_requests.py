# handlers/btg_requests.py
import asyncio
import json

# Imports from Layer (/opt/python/python/)
# btg, hubspot, aws, src are provided by SharedLibrariesLayer
from src.etl.workflows.request_btg_report import RequestBTGAPIWorkflow


def lambda_handler(event, context=None):
    print("=" * 60)
    print("BTG REQUESTS HANDLER - handlers/btg_requests.py")
    print("=" * 60)
    print(f"Received event: {json.dumps(event, default=str)}")

    # report_type opcional — formato kebab-case do BTG (ex: "rm-reports-banking").
    # Se ausente ou None: requisita todos os relatórios configurados.
    # Se presente: requisita apenas aquele tipo específico.
    report_type = event.get("report_type") if isinstance(event, dict) else None

    if report_type:
        print(f"Targeted run: report_type={report_type}")
    else:
        print("Full run: requesting all configured reports")

    workflow = RequestBTGAPIWorkflow()
    results = asyncio.run(workflow.run_requests(report_type=report_type))

    success = all(r["status"] in ("requested", "skipped") for r in results.values())

    return {
        'statusCode': 200 if success else 207,
        'body': json.dumps({
            'message': 'BTG reports requested',
            'report_type': report_type or 'all',
            'results': results,
        }, default=str)
    }


def lambda_test(event, context=None):
    pass
