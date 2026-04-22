from fastapi import APIRouter, HTTPException

from app.models.schemas import LeadInput, FinalDecisionOutput
from app.services.orchestrator import Orchestrator
from app.utils.logger import get_logger

router = APIRouter()
log = get_logger("routes")

orchestrator = Orchestrator()


@router.post("/process-lead", response_model=FinalDecisionOutput)
def process_lead(payload: LeadInput):
    """Run a lead through all agents and return the combined decision package."""
    log.info(f"Incoming lead | source={payload.source} urgency={payload.urgency}")
    try:
        result = orchestrator.run(payload)
        return result
    except Exception as e:
        log.exception("Orchestrator failed")
        raise HTTPException(status_code=500, detail=f"Agent pipeline error: {e}")


@router.get("/sample-leads")
def sample_leads():
    """Focused pool of 12 leads — weighted toward septic, roofing, and HVAC (our target verticals)."""
    return [
        # --- Septic (4) ---
        {"vertical": "septic", "label": "Septic — pumping emergency", "contact_name": "Darlene Hatcher", "contact_email": "darlene@hatcherseptic.com",
         "message": "My septic company in rural Georgia is buried. We get 30-40 calls a day in summer and miss a third. Need something that answers 24/7 and books jobs.",
         "source": "facebook lead ad", "urgency": "high", "service_requested": "24/7 lead response", "budget": "$1,500/mo"},

        {"vertical": "septic", "label": "Septic — install quote", "contact_name": "Ray Kowalski", "contact_email": "ray@kowalskipumping.com",
         "message": "Septic & drain service, 4 trucks. Homeowner just requested a new install quote — $8k job. Want to make sure these leads don't sit overnight.",
         "source": "website form", "urgency": "high", "service_requested": "after-hours lead capture"},

        {"vertical": "septic", "label": "Septic — shopping", "contact_name": "Tina Browne", "contact_email": "tina@brownesepticllc.com",
         "message": "Small septic business, two techs. Looking at what's out there for follow-up automation. What's pricing look like?",
         "source": "google ad", "urgency": "medium", "service_requested": "follow-up automation"},

        {"vertical": "septic", "label": "Septic — curious", "contact_name": "—", "contact_email": "office@mainestreet-septic.com",
         "message": "Saw this on a webinar. What exactly does it do?",
         "source": "newsletter", "urgency": "low"},

        # --- Roofing (4) ---
        {"vertical": "roofing", "label": "Roofing — storm surge", "contact_name": "Mike Calloway", "contact_email": "mike@calloway-roofing.com",
         "message": "Hail hit our city last Tuesday. We're getting 60+ inspection requests a day and losing half of them to slow callbacks. Need help THIS WEEK.",
         "source": "phone inquiry", "urgency": "high", "service_requested": "inbound triage + booking", "budget": "$3k/mo"},

        {"vertical": "roofing", "label": "Roofing — commercial", "contact_name": "Jaylen Briggs", "contact_email": "jay@briggsroofingco.com",
         "message": "Commercial roofing company. Our avg contract is $45k. Losing bids because we reply too slow. What would a setup look like?",
         "source": "linkedin message", "urgency": "high", "service_requested": "commercial lead qualification"},

        {"vertical": "roofing", "label": "Roofing — pricing curious", "contact_name": "Alyssa Chen", "contact_email": "alyssa@chenroofing.net",
         "message": "Hey, we run a residential roofing company. Saw your site. What's pricing for a 6-person shop?",
         "source": "website form", "urgency": "medium", "service_requested": "pricing info"},

        {"vertical": "roofing", "label": "Roofing — just browsing", "contact_name": "—", "contact_email": "curious@gmail.com",
         "message": "Just poking around. Cool concept.",
         "source": "google ad", "urgency": "low"},

        # --- HVAC (4) ---
        {"vertical": "hvac", "label": "HVAC — peak season", "contact_name": "Brian Holt", "contact_email": "brian@holtair.com",
         "message": "HVAC company in Phoenix. Peak summer starts in weeks and my front desk can't keep up with call volume. Need to qualify inbound and auto-book service calls.",
         "source": "facebook lead ad", "urgency": "high", "service_requested": "qualification + booking", "budget": "$1,500/mo"},

        {"vertical": "hvac", "label": "HVAC — emergency repairs", "contact_name": "Priya Shah", "contact_email": "priya@shahhvac.com",
         "message": "24/7 HVAC repair. Avg emergency call is $800-$1,500. When we don't answer at 2am, customers go to the next company. Need instant response.",
         "source": "instagram dm", "urgency": "high", "service_requested": "after-hours auto-response", "budget": "$2k/mo"},

        {"vertical": "hvac", "label": "HVAC — shopping around", "contact_name": "Tom Delgado", "contact_email": "tom@delgadohvacpro.com",
         "message": "Small HVAC contractor, three trucks. Want to see a demo. What's your cheapest plan?",
         "source": "referral", "urgency": "medium", "service_requested": "demo + pricing"},

        {"vertical": "hvac", "label": "HVAC — no budget", "contact_name": "—", "contact_email": "maybelater@gmail.com",
         "message": "Interesting but no budget right now. Maybe later this year.",
         "source": "newsletter", "urgency": "low"},
    ]
