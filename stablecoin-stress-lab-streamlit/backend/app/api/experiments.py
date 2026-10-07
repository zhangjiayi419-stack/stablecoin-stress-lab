from fastapi import APIRouter, HTTPException

from backend.app.domain.schemas import AgentExperimentRequest, QuoteRequest, QuoteResponse
from backend.app.services.agents import simulate_agents
from backend.app.services.experiment import calculate_experiment

router = APIRouter(prefix="/api", tags=["Experiments"])


@router.post("/quote", response_model=QuoteResponse)
def quote(request: QuoteRequest) -> dict:
    try:
        return calculate_experiment(request)
    except LookupError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/agents/simulate")
def simulate_agent_scenario(request: AgentExperimentRequest) -> dict:
    try:
        return simulate_agents(request)
    except LookupError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post('/agents/phase-diagram')
def agent_phase_diagram(request: AgentExperimentRequest) -> dict:
    from backend.app.services.agents import phase_diagram
    try:
        return phase_diagram(request)
    except LookupError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


from backend.app.domain.schemas import PortfolioRequest
from backend.app.services.portfolio import portfolio_stress


@router.post('/portfolio/stress')
def retail_portfolio_stress(request: PortfolioRequest):
    try:
        return portfolio_stress(request)
    except LookupError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post('/risk-assistant/analyze')
def risk_assistant(request: PortfolioRequest):
    from backend.app.services.portfolio import risk_workflow
    try:
        return risk_workflow(request)
    except LookupError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
