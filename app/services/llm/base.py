from abc import ABC, abstractmethod
from typing import List, Dict, Tuple
from app.domain.recipes import Recipe, CustomFinish
from app.domain.recommendations import IndividualClinicalRationale

class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate_clinical_reasoning(
        self,
        recipe: Recipe,
        contexts: list, # List[MemberProfileContext]
        assigned_finishes: Dict[str, CustomFinish]
    ) -> Tuple[str, List[IndividualClinicalRationale]]:
        """
        Generates group consensus rationale and individual clinical rationales for each participating member.
        Returns: (overall_summary, list_of_individual_rationales)
        """
        pass
