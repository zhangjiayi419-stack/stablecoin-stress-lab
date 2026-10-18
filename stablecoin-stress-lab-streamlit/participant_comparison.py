"""One request, one engine and explicit metrics for path/grid comparisons."""
import hashlib
import json
from backend.app.domain.schemas import AgentExperimentRequest
from backend.app.services.agents import simulate_agents

VERSION='cohort-comparison-1.0'

def request_fingerprint(request):
    payload=request.model_dump(mode='json') if hasattr(request,'model_dump') else request
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def matched_phase_diagram(request: AgentExperimentRequest):
    # Include the selected coordinates rather than interpolate an absent cell.
    depths=sorted(set([.25,.5,1.,1.5,2.,3.,request.pool_liquidity_multiplier]))
    pressures=sorted(set([0.,1.,3.,5.,10.,20.,30.,request.redemption_pressure_pct]))
    fields=['max_depeg_depth_pct','max_premium_pct','max_absolute_deviation_pct','max_move_from_initial_pct','recovery_hour','recovery_hours_after_trough']
    cells=[]
    for depth in depths:
        for pressure in pressures:
            scenario=request.model_copy(update=dict(pool_liquidity_multiplier=depth,redemption_pressure_pct=pressure))
            result=simulate_agents(scenario)
            cells.append(dict(liquidity_multiplier=depth,redemption_pressure_pct=pressure,**{k:result['summary'][k] for k in fields}))
    return dict(version=VERSION,request_sha256=request_fingerprint(request),assumptions=request.model_dump(mode='json'),cells=cells,
        metric_definition='max_move_from_initial_pct = 100 * max_t |P_t - P_initial|; percentage points of USD 1, not relative percent return. max_depeg_depth_pct = 100 * max(0, 1 - min_t P_t). All non-axis assumptions are identical to the displayed path.')


def selected_cell(phase,request):
    if phase['request_sha256']!=request_fingerprint(request):raise ValueError('Path and sensitivity grid have different submitted assumptions.')
    return next(c for c in phase['cells'] if c['liquidity_multiplier']==request.pool_liquidity_multiplier and c['redemption_pressure_pct']==request.redemption_pressure_pct)
