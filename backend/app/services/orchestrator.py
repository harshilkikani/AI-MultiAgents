import time

from app.models.schemas import (
    LeadInput,
    FinalDecisionOutput,
    AgentLog,
)
from app.services.agents.intake_agent import IntakeAgent
from app.services.agents.qualification_agent import QualificationAgent
from app.services.agents.response_agent import ResponseAgent
from app.services.agents.followup_agent import FollowUpAgent
from app.services.agents.action_agent import ActionAgent
from app.services.agents.manager_agent import ManagerAgent
from app.utils.logger import get_logger


class Orchestrator:
    """Coordinates all specialist agents and produces the final decision package."""

    def __init__(self):
        self.log = get_logger("orchestrator")
        self.intake = IntakeAgent()
        self.qualification = QualificationAgent()
        self.response = ResponseAgent()
        self.follow_up = FollowUpAgent()
        self.action = ActionAgent()
        self.manager = ManagerAgent()

    def _timed(self, name: str, fn, logs: list):
        start = time.time()
        try:
            out = fn()
            logs.append(AgentLog(
                agent=name, status="ok",
                duration_ms=int((time.time() - start) * 1000),
            ))
            return out
        except Exception as e:
            logs.append(AgentLog(
                agent=name, status="error",
                duration_ms=int((time.time() - start) * 1000),
                note=str(e),
            ))
            raise

    def run(self, lead: LeadInput) -> FinalDecisionOutput:
        logs: list[AgentLog] = []
        self.log.info("=== orchestrator run starting ===")

        intake_out = self._timed("Intake Agent",
            lambda: self.intake.process(lead), logs)

        qualification_out = self._timed("Qualification Agent",
            lambda: self.qualification.process(intake_out), logs)

        response_out = self._timed("Response Agent",
            lambda: self.response.process(intake_out, qualification_out), logs)

        follow_up_out = self._timed("Follow-Up Agent",
            lambda: self.follow_up.process(intake_out, qualification_out, response_out), logs)

        action_out = self._timed("Action Agent",
            lambda: self.action.process(intake_out, qualification_out, response_out, follow_up_out),
            logs)

        manager_summary = self._timed("Manager Agent",
            lambda: self.manager.process(
                intake_out, qualification_out, response_out, follow_up_out, action_out
            ), logs)

        self.log.info("=== orchestrator run complete ===")

        return FinalDecisionOutput(
            lead_input=lead,
            intake=intake_out,
            qualification=qualification_out,
            response=response_out,
            follow_up=follow_up_out,
            action=action_out,
            manager_summary=manager_summary,
            logs=logs,
        )
