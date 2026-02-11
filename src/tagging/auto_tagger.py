"""
Auto-tagger orchestrator for Kenyan financial content.

Classifies content along 5 dimensions:
1. Persona: Who is this content for?
2. Life stage: What financial literacy level?
3. Risk level: What risk level does this content discuss?
4. Product type: What financial products?
5. Relevance score: How useful/specific is this content?

Usage:
    tagger = AutoTagger()
    result = tagger.tag(text, metadata)
    metadata = tagger.tag_to_metadata(text, metadata)
"""

from dataclasses import dataclass
from typing import List, Dict

from src.tagging.persona_rules import classify_persona
from src.tagging.product_rules import classify_product_types
from src.tagging.risk_rules import classify_risk_level
from src.tagging.life_stage_rules import classify_life_stage
from src.tagging.relevance_scorer import score_relevance


@dataclass
class TagResult:
    """Result of auto-tagging a document or chunk."""
    persona: List[str]
    life_stage: str
    risk_level: str
    product_types: List[str]
    relevance_score: float


class AutoTagger:
    """
    Rule-based content classifier for Kenyan financial documents.

    Uses keyword matching optimized for Kenyan financial terminology.
    No ML model needed — the domain is narrow enough for high-precision rules.
    """

    def tag(self, text: str, metadata: Dict) -> TagResult:
        """
        Tag a document or chunk with all classification dimensions.

        Args:
            text: Document or chunk text (first ~3000 chars is sufficient)
            metadata: Existing metadata (source_id, institution_type, etc.)

        Returns:
            TagResult with all classifications
        """
        # Combine text with title/section for better classification
        title = metadata.get("title", "")
        section = metadata.get("section_title", "")
        context = f"{title} {section} {text}"

        source_id = metadata.get("source_id", "")
        institution_type = metadata.get("institution_type", "")

        return TagResult(
            persona=classify_persona(context, source_id, institution_type),
            life_stage=classify_life_stage(context, source_id, institution_type),
            risk_level=classify_risk_level(context, source_id, institution_type),
            product_types=classify_product_types(context, source_id, institution_type),
            relevance_score=score_relevance(text, metadata),
        )

    def tag_to_metadata(self, text: str, metadata: Dict) -> Dict:
        """
        Tag and merge results into a metadata dict.

        Modifies metadata in-place and returns it.
        Persona and product_types are stored as comma-separated strings
        for FAISS metadata compatibility.
        """
        result = self.tag(text, metadata)
        metadata["persona"] = ",".join(result.persona) if result.persona else "general"
        metadata["life_stage"] = result.life_stage
        metadata["risk_level"] = result.risk_level
        metadata["product_type"] = ",".join(result.product_types) if result.product_types else ""
        metadata["relevance_score"] = result.relevance_score
        return metadata
