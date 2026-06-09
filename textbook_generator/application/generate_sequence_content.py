import logging
from ..domain.models import GenerationStatus, Textbook
from ..domain.repositories import TextbookRepository
from ..domain.services import TextbookAgentService

logger = logging.getLogger(__name__)

class GenerateSequenceContentUseCase:
    def __init__(
        self,
        textbook_repo: TextbookRepository,
        agent_service: TextbookAgentService
    ):
        self.textbook_repo = textbook_repo
        self.agent_service = agent_service

    def execute(
        self, 
        textbook: Textbook, 
        secuencia_id: int, 
        trimester_num: int,
        title: str, 
        objectives: str, 
        requirements: list
    ) -> None:
        logger.info(f"Generating content for Sequence ID {secuencia_id}: '{title}'")
        
        # 1. Update sequence status to GENERATING
        sec = self.textbook_repo.get_secuencia(secuencia_id)
        if not sec:
            return
        sec.status = GenerationStatus.GENERATING
        self.textbook_repo.update_secuencia(sec)

        try:
            # 2. Call agent to generate lesson details (Inicio, Desarrollo, Cierre)
            lessons = self.agent_service.generate_sequence_content(
                subject=textbook.subject,
                grade=textbook.grade,
                trimester_num=trimester_num,
                seq_num=sec.number,
                seq_title=title,
                seq_objectives=objectives,
                requirements=requirements
            )
            
            # 3. Save generated lessons
            for idx, lesson in enumerate(lessons):
                lesson.secuencia_id = secuencia_id
                lesson.number = idx + 1
                self.textbook_repo.create_lesson(lesson)

            # 4. Evaluate generated content via independent judge agent
            sec_with_lessons = self.textbook_repo.get_secuencia_with_lessons(secuencia_id)
            eval_result = self.agent_service.evaluate_sequence(sec_with_lessons, requirements)
            
            # 5. Save evaluation metrics and auditor justification
            sec_with_lessons.curricular_alignment_score = eval_result.alignment_score
            sec_with_lessons.age_appropriateness_score = eval_result.age_score
            sec_with_lessons.review_feedback = eval_result.justification
            
            # 6. Apply quality threshold check (0.85/1.00)
            if eval_result.alignment_score >= 0.85 and eval_result.age_score >= 0.85:
                sec_with_lessons.status = GenerationStatus.APPROVED
                logger.info(f"Sequence {secuencia_id} auto-approved ({eval_result.alignment_score}/{eval_result.age_score})")
            else:
                sec_with_lessons.status = GenerationStatus.PENDING_REVIEW
                logger.warning(f"Sequence {secuencia_id} routed to HITL ({eval_result.alignment_score}/{eval_result.age_score})")
            
            # Save final sequence state
            self.textbook_repo.update_secuencia(sec_with_lessons)

        except Exception as e:
            logger.exception(f"Failed to generate content for sequence {secuencia_id}")
            sec.status = GenerationStatus.REJECTED
            sec.review_feedback = f"Generation error: {str(e)}"
            self.textbook_repo.update_secuencia(sec)
