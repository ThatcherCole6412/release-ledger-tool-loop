"""HTTP boundary for the release automation loop."""

from fastapi import FastAPI

from release_operator import AutomationRequest, AutomationResult, run_automation

service = FastAPI(title="Release automation operator")


@service.post("/automation/run", response_model=AutomationResult)
def automate_release(request: AutomationRequest) -> AutomationResult:
    return run_automation(request)
