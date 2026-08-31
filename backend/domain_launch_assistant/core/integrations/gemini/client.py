from django.conf import settings
from google import genai
from google.genai import errors, types
from pydantic import BaseModel


class BrandIdeaOutput(BaseModel):
    name: str
    description: str


class BrandIdeasOutput(BaseModel):
    brands: list[BrandIdeaOutput]


class DomainRecommendationOutput(BaseModel):
    recommended_domain_id: str
    reasoning: str


class GeminiClientError(Exception):
    """
    Raised when communication with Gemini fails.
    """
    pass


class GeminiClient:
    """
    Client responsible only for communicating with Gemini.

    This class does not know about:
    - Django models
    - DRF
    - HTTP responses
    - users
    - projects
    """

    def __init__(self):
        self.client = genai.Client(
            api_key=settings.GEMINI_API_KEY,
        )

    def generate_brand_ideas(
        self,
        business_description: str,
        count: int,
    ) -> dict:
        prompt = f"""
Generate {count} unique brand name ideas for the following business.

Business description:
{business_description}

For every brand:
- Provide a memorable brand name.
- Provide a short explanation of why the name fits the business.

Return only the requested structured output.
"""
        try:
            response = self.client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=BrandIdeasOutput,
                ),
            )
            result = BrandIdeasOutput.model_validate_json(response.text)
            return result.model_dump()
        except errors.APIError as exc:
            raise GeminiClientError(
                f"Gemini API request failed: {exc}"
            ) from exc
        except Exception as exc:
            raise GeminiClientError(
                f"Gemini brand generation failed: {exc}"
            ) from exc

    def recommend_domain(
        self,
        business_description: str,
        domains: list[dict],
    ) -> dict:
        """
        domains: list of {"id": str, "domain": str} — only AVAILABLE
        DomainResults for the project. Passing the real id (rather than
        just the domain string) is what lets the caller validate the
        response against real rows afterwards.
        """
        domain_list = "\n".join(
            f"- id: {d['id']}, domain: {d['domain']}" for d in domains
        )
        prompt = f"""
Given the business below and a list of available domain names, pick the
single best domain for this business to launch with.

Business description:
{business_description}

Available domains (recommended_domain_id must be exactly one of these ids):
{domain_list}

Return only the requested structured output.
"""
        try:
            response = self.client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=DomainRecommendationOutput,
                ),
            )
            result = DomainRecommendationOutput.model_validate_json(response.text)
            return result.model_dump()
        except errors.APIError as exc:
            raise GeminiClientError(
                f"Gemini API request failed: {exc}"
            ) from exc
        except Exception as exc:
            raise GeminiClientError(
                f"Gemini domain recommendation failed: {exc}"
            ) from exc