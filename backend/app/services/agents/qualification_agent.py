from app.models.schemas import IntakeOutput, QualificationOutput
from app.services.agents.base import BaseAgent


class QualificationAgent(BaseAgent):
    name = "Qualification Agent"
    prompt_file = "qualification_prompt.txt"
    output_model = QualificationOutput

    def process(self, intake: IntakeOutput) -> QualificationOutput:
        user_prompt = (
            "Qualify this lead based on the structured intake record below.\n\n"
            f"{intake.model_dump_json(indent=2)}"
        )
        return self.run(user_prompt)
