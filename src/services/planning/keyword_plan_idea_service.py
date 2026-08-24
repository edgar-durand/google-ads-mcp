"""Keyword plan idea service implementation using Google Ads SDK."""

from typing import Any, Dict, List, Optional, Callable, Awaitable

from fastmcp import Context, FastMCP
from google.ads.googleads.v23.services.services.keyword_plan_idea_service import (
    KeywordPlanIdeaServiceClient,
)
from google.ads.googleads.v23.services.types.keyword_plan_idea_service import (
    BiddableKeyword,
    CampaignToForecast,
    CriterionBidModifier,
    ForecastAdGroup,
    GenerateKeywordForecastMetricsRequest,
    GenerateKeywordHistoricalMetricsRequest,
    GenerateKeywordHistoricalMetricsResult,
    GenerateKeywordIdeasRequest,
    GenerateKeywordIdeaResult,
    KeywordAndUrlSeed,
    KeywordSeed,
    ManualCpcBiddingStrategy,
    MaximizeClicksBiddingStrategy,
    MaximizeConversionsBiddingStrategy,
    SiteSeed,
    UrlSeed,
)
from google.ads.googleads.v23.common.types.criteria import KeywordInfo
from google.ads.googleads.v23.common.types.dates import DateRange
from google.ads.googleads.v23.enums.types.keyword_match_type import (
    KeywordMatchTypeEnum,
)
from google.ads.googleads.v23.enums.types.keyword_plan_network import (
    KeywordPlanNetworkEnum,
)
from google.ads.googleads.errors import GoogleAdsException

from src.sdk_client import get_sdk_client
from src.utils import (
    RATE_LIMIT_MSG,
    resolve_enum,
    format_ads_error,
    format_customer_id,
    get_logger,
    ensure_list,
    is_resource_exhausted,
)

logger = get_logger(__name__)


class KeywordPlanIdeaService:
    """Keyword plan idea service for keyword research and discovery."""

    def __init__(self) -> None:
        """Initialize the keyword plan idea service."""
        self._client: Optional[KeywordPlanIdeaServiceClient] = None

    @property
    def client(self) -> KeywordPlanIdeaServiceClient:
        """Get the keyword plan idea service client."""
        if self._client is None:
            sdk_client = get_sdk_client()
            self._client = sdk_client.client.get_service(
                "KeywordPlanIdeaService", version="v23"
            )
        assert self._client is not None
        return self._client

    async def generate_keyword_ideas_from_keywords(
        self,
        ctx: Context,
        customer_id: str,
        keywords: List[str],
        language: str,
        geo_target_constants: List[str],
        keyword_plan_network: KeywordPlanNetworkEnum.KeywordPlanNetwork = KeywordPlanNetworkEnum.KeywordPlanNetwork.GOOGLE_SEARCH_AND_PARTNERS,
        include_adult_keywords: bool = False,
        page_size: int = 100,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate keyword ideas from seed keywords.

        Args:
            ctx: FastMCP context
            customer_id: The customer ID
            keywords: List of seed keywords
            language: Language constant resource name (e.g., "languageConstants/1000" for English)
            geo_target_constants: List of geo target constant resource names
            keyword_plan_network: Network type (UNSPECIFIED, GOOGLE_SEARCH, GOOGLE_SEARCH_AND_PARTNERS)
            include_adult_keywords: Whether to include adult keywords
            page_size: Number of results per page

        Returns:
            List of keyword ideas with metrics
        """
        try:
            customer_id = format_customer_id(customer_id)
            # Create request
            request = GenerateKeywordIdeasRequest()
            request.customer_id = customer_id
            request.language = language
            request.geo_target_constants.extend(geo_target_constants)
            request.include_adult_keywords = include_adult_keywords
            request.page_size = page_size
            if page_token:
                request.page_token = page_token
            # Set keyword plan network using enum
            request.keyword_plan_network = keyword_plan_network

            # Create keyword seed
            keyword_seed = KeywordSeed()
            keyword_seed.keywords.extend(keywords)
            request.keyword_seed = keyword_seed

            # Generate ideas — only take the first page to avoid
            # burning through the 1 QPS planning quota with auto-pagination.
            pager = self.client.generate_keyword_ideas(request=request)
            first_page = next(pager.pages)

            keyword_ideas = [
                self._format_keyword_idea(idea) for idea in first_page.results
            ]

            result: Dict[str, Any] = {"results": keyword_ideas}
            if first_page.next_page_token:
                result["next_page_token"] = first_page.next_page_token

            await ctx.log(
                level="info",
                message=f"Generated {len(keyword_ideas)} keyword ideas from {len(keywords)} seed keywords",
            )

            return result

        except GoogleAdsException as e:
            error_msg = format_ads_error(e)
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e
        except Exception as e:
            if is_resource_exhausted(e):
                await ctx.log(level="error", message=RATE_LIMIT_MSG)
                raise Exception(RATE_LIMIT_MSG) from e
            error_msg = f"Failed to generate keyword ideas: {str(e)}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e

    async def generate_keyword_ideas_from_url(
        self,
        ctx: Context,
        customer_id: str,
        page_url: str,
        language: str,
        geo_target_constants: List[str],
        keyword_plan_network: KeywordPlanNetworkEnum.KeywordPlanNetwork = KeywordPlanNetworkEnum.KeywordPlanNetwork.GOOGLE_SEARCH_AND_PARTNERS,
        include_adult_keywords: bool = False,
        page_size: int = 100,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate keyword ideas from a URL.

        Args:
            ctx: FastMCP context
            customer_id: The customer ID
            page_url: The URL to analyze
            language: Language constant resource name
            geo_target_constants: List of geo target constant resource names
            keyword_plan_network: Network type
            include_adult_keywords: Whether to include adult keywords
            page_size: Number of results per page

        Returns:
            List of keyword ideas with metrics
        """
        try:
            customer_id = format_customer_id(customer_id)
            # Create request
            request = GenerateKeywordIdeasRequest()
            request.customer_id = customer_id
            request.language = language
            request.geo_target_constants.extend(geo_target_constants)
            request.include_adult_keywords = include_adult_keywords
            request.page_size = page_size
            if page_token:
                request.page_token = page_token
            # Set keyword plan network using enum
            request.keyword_plan_network = keyword_plan_network

            # Create URL seed
            url_seed = UrlSeed()
            url_seed.url = page_url
            request.url_seed = url_seed

            # Generate ideas — first page only (1 QPS planning quota)
            pager = self.client.generate_keyword_ideas(request=request)
            first_page = next(pager.pages)

            keyword_ideas = [
                self._format_keyword_idea(idea) for idea in first_page.results
            ]

            result: Dict[str, Any] = {"results": keyword_ideas}
            if first_page.next_page_token:
                result["next_page_token"] = first_page.next_page_token

            await ctx.log(
                level="info",
                message=f"Generated {len(keyword_ideas)} keyword ideas from URL: {page_url}",
            )

            return result

        except GoogleAdsException as e:
            error_msg = format_ads_error(e)
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e
        except Exception as e:
            if is_resource_exhausted(e):
                await ctx.log(level="error", message=RATE_LIMIT_MSG)
                raise Exception(RATE_LIMIT_MSG) from e
            error_msg = f"Failed to generate keyword ideas from URL: {str(e)}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e

    async def generate_keyword_ideas_from_site(
        self,
        ctx: Context,
        customer_id: str,
        site_url: str,
        language: str,
        geo_target_constants: List[str],
        keyword_plan_network: KeywordPlanNetworkEnum.KeywordPlanNetwork = KeywordPlanNetworkEnum.KeywordPlanNetwork.GOOGLE_SEARCH_AND_PARTNERS,
        include_adult_keywords: bool = False,
        page_size: int = 100,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate keyword ideas from an entire website.

        Args:
            ctx: FastMCP context
            customer_id: The customer ID
            site_url: The website URL to analyze (domain only)
            language: Language constant resource name
            geo_target_constants: List of geo target constant resource names
            keyword_plan_network: Network type
            include_adult_keywords: Whether to include adult keywords
            page_size: Number of results per page

        Returns:
            List of keyword ideas with metrics
        """
        try:
            customer_id = format_customer_id(customer_id)
            # Create request
            request = GenerateKeywordIdeasRequest()
            request.customer_id = customer_id
            request.language = language
            request.geo_target_constants.extend(geo_target_constants)
            request.include_adult_keywords = include_adult_keywords
            request.page_size = page_size
            if page_token:
                request.page_token = page_token
            # Set keyword plan network using enum
            request.keyword_plan_network = keyword_plan_network

            # Create site seed
            site_seed = SiteSeed()
            site_seed.site = site_url
            request.site_seed = site_seed

            # Generate ideas — first page only (1 QPS planning quota)
            pager = self.client.generate_keyword_ideas(request=request)
            first_page = next(pager.pages)

            keyword_ideas = [
                self._format_keyword_idea(idea) for idea in first_page.results
            ]

            result: Dict[str, Any] = {"results": keyword_ideas}
            if first_page.next_page_token:
                result["next_page_token"] = first_page.next_page_token

            await ctx.log(
                level="info",
                message=f"Generated {len(keyword_ideas)} keyword ideas from site: {site_url}",
            )

            return result

        except GoogleAdsException as e:
            error_msg = format_ads_error(e)
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e
        except Exception as e:
            if is_resource_exhausted(e):
                await ctx.log(level="error", message=RATE_LIMIT_MSG)
                raise Exception(RATE_LIMIT_MSG) from e
            error_msg = f"Failed to generate keyword ideas from site: {str(e)}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e

    async def generate_keyword_ideas_from_keywords_and_url(
        self,
        ctx: Context,
        customer_id: str,
        keywords: List[str],
        page_url: str,
        language: str,
        geo_target_constants: List[str],
        keyword_plan_network: KeywordPlanNetworkEnum.KeywordPlanNetwork = KeywordPlanNetworkEnum.KeywordPlanNetwork.GOOGLE_SEARCH_AND_PARTNERS,
        include_adult_keywords: bool = False,
        page_size: int = 100,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate keyword ideas from both keywords and a URL.

        Args:
            ctx: FastMCP context
            customer_id: The customer ID
            keywords: List of seed keywords
            page_url: The URL to analyze
            language: Language constant resource name
            geo_target_constants: List of geo target constant resource names
            keyword_plan_network: Network type
            include_adult_keywords: Whether to include adult keywords
            page_size: Number of results per page

        Returns:
            List of keyword ideas with metrics
        """
        try:
            customer_id = format_customer_id(customer_id)
            # Create request
            request = GenerateKeywordIdeasRequest()
            request.customer_id = customer_id
            request.language = language
            request.geo_target_constants.extend(geo_target_constants)
            request.include_adult_keywords = include_adult_keywords
            request.page_size = page_size
            if page_token:
                request.page_token = page_token
            # Set keyword plan network using enum
            request.keyword_plan_network = keyword_plan_network

            # Create keyword and URL seed
            keyword_and_url_seed = KeywordAndUrlSeed()
            keyword_and_url_seed.keywords.extend(keywords)
            keyword_and_url_seed.url = page_url
            request.keyword_and_url_seed = keyword_and_url_seed

            # Generate ideas — first page only (1 QPS planning quota)
            pager = self.client.generate_keyword_ideas(request=request)
            first_page = next(pager.pages)

            keyword_ideas = [
                self._format_keyword_idea(idea) for idea in first_page.results
            ]

            result: Dict[str, Any] = {"results": keyword_ideas}
            if first_page.next_page_token:
                result["next_page_token"] = first_page.next_page_token

            await ctx.log(
                level="info",
                message=f"Generated {len(keyword_ideas)} keyword ideas from keywords and URL",
            )

            return result

        except GoogleAdsException as e:
            error_msg = format_ads_error(e)
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e
        except Exception as e:
            if is_resource_exhausted(e):
                await ctx.log(level="error", message=RATE_LIMIT_MSG)
                raise Exception(RATE_LIMIT_MSG) from e
            error_msg = f"Failed to generate keyword ideas: {str(e)}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e

    async def generate_keyword_historical_metrics(
        self,
        ctx: Context,
        customer_id: str,
        keywords: List[str],
        language: str,
        geo_target_constants: List[str],
        keyword_plan_network: KeywordPlanNetworkEnum.KeywordPlanNetwork = KeywordPlanNetworkEnum.KeywordPlanNetwork.GOOGLE_SEARCH,
        include_adult_keywords: bool = False,
        aggregate_metrics: bool = False,
    ) -> Dict[str, Any]:
        """Get historical search metrics for an EXPLICIT list of keywords.

        Unlike ``generate_keyword_ideas_*`` this does not expand the seeds — it
        returns metrics for exactly the keywords supplied (plus their close
        variants), which is what you want when scoring a candidate keyword list.

        Args:
            ctx: FastMCP context
            customer_id: The customer ID
            keywords: The exact keywords to look up (max 10,000)
            language: Language constant resource name (e.g., "languageConstants/1000")
            geo_target_constants: List of geo target constant resource names
            keyword_plan_network: Network type
            include_adult_keywords: Whether to include adult keywords
            aggregate_metrics: Aggregate close-variant volumes into the keyword

        Returns:
            Dict with a ``results`` list of {text, close_variants, keyword_metrics}
        """
        try:
            customer_id = format_customer_id(customer_id)

            request = GenerateKeywordHistoricalMetricsRequest()
            request.customer_id = customer_id
            request.keywords.extend(keywords)
            request.language = language
            request.geo_target_constants.extend(geo_target_constants)
            request.keyword_plan_network = keyword_plan_network
            request.include_adult_keywords = include_adult_keywords
            if aggregate_metrics:
                request.aggregate_metrics.include_average_cpc = True

            response = self.client.generate_keyword_historical_metrics(request=request)

            results = [
                self._format_historical_metrics_result(result)
                for result in response.results
            ]

            await ctx.log(
                level="info",
                message=f"Fetched historical metrics for {len(results)} keywords",
            )

            return {"results": results}

        except GoogleAdsException as e:
            error_msg = format_ads_error(e)
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e
        except Exception as e:
            if is_resource_exhausted(e):
                await ctx.log(level="error", message=RATE_LIMIT_MSG)
                raise Exception(RATE_LIMIT_MSG) from e
            error_msg = f"Failed to generate keyword historical metrics: {str(e)}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e

    async def generate_keyword_forecast_metrics(
        self,
        ctx: Context,
        customer_id: str,
        keywords: List[str],
        currency_code: str,
        start_date: str,
        end_date: str,
        language_constants: List[str],
        geo_target_constants: List[str],
        bidding_strategy: str = "MAXIMIZE_CLICKS",
        daily_budget_micros: Optional[int] = None,
        max_cpc_bid_micros: Optional[int] = None,
        match_type: KeywordMatchTypeEnum.KeywordMatchType = KeywordMatchTypeEnum.KeywordMatchType.PHRASE,
        keyword_plan_network: KeywordPlanNetworkEnum.KeywordPlanNetwork = KeywordPlanNetworkEnum.KeywordPlanNetwork.GOOGLE_SEARCH,
        negative_keywords: Optional[List[str]] = None,
        conversion_rate: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Forecast impressions/clicks/cost for a keyword set at a daily budget.

        This is the v23 replacement for the removed
        ``KeywordPlanService.GenerateForecastMetrics``: it is READ-ONLY and
        creates no KeywordPlan resources.

        Args:
            ctx: FastMCP context
            customer_id: The customer ID
            keywords: Keywords to forecast
            currency_code: Three-letter currency code (e.g., "USD")
            start_date: Forecast start date, "YYYY-MM-DD" (must be in the future)
            end_date: Forecast end date, "YYYY-MM-DD"
            language_constants: Language constant resource names
            geo_target_constants: Geo target constant resource names
            bidding_strategy: MAXIMIZE_CLICKS, MAXIMIZE_CONVERSIONS or MANUAL_CPC
            daily_budget_micros: Daily budget/target spend in micros (USD × 1,000,000)
            max_cpc_bid_micros: Max CPC bid in micros. Under MANUAL_CPC this is
                the keyword/ad-group bid; under MAXIMIZE_* it is only applied as
                the strategy's bid ceiling (keyword-level bids are rejected there)
            match_type: Match type applied to every keyword
            keyword_plan_network: Network type
            negative_keywords: Campaign-level negative keywords
            conversion_rate: Assumed conversion rate (0-1) to derive conversions

        Returns:
            Dict with ``campaign_forecast_metrics`` (impressions, clicks, cost, …)
        """
        try:
            customer_id = format_customer_id(customer_id)

            campaign = CampaignToForecast()
            campaign.language_constants.extend(language_constants)
            campaign.keyword_plan_network = keyword_plan_network
            for geo in geo_target_constants:
                modifier = CriterionBidModifier()
                modifier.geo_target_constant = geo
                campaign.geo_modifiers.append(modifier)

            strategy = bidding_strategy.upper()
            # Per-keyword / per-ad-group max CPC bids are ONLY accepted with
            # MANUAL_CPC. Sending them alongside an automated strategy is
            # rejected with keyword_plan_idea_error: INVALID_VALUE, so under
            # MAXIMIZE_* the bid is applied as a ceiling on the strategy only.
            bid_keywords = strategy == "MANUAL_CPC"
            if strategy == "MAXIMIZE_CLICKS":
                max_clicks = MaximizeClicksBiddingStrategy()
                if daily_budget_micros is not None:
                    max_clicks.daily_target_spend_micros = daily_budget_micros
                if max_cpc_bid_micros is not None:
                    max_clicks.max_cpc_bid_ceiling_micros = max_cpc_bid_micros
                campaign.bidding_strategy.maximize_clicks_bidding_strategy = max_clicks
            elif strategy == "MAXIMIZE_CONVERSIONS":
                max_conv = MaximizeConversionsBiddingStrategy()
                if daily_budget_micros is not None:
                    max_conv.daily_target_spend_micros = daily_budget_micros
                campaign.bidding_strategy.maximize_conversions_bidding_strategy = (
                    max_conv
                )
            elif strategy == "MANUAL_CPC":
                manual = ManualCpcBiddingStrategy()
                if daily_budget_micros is not None:
                    manual.daily_budget_micros = daily_budget_micros
                if max_cpc_bid_micros is not None:
                    manual.max_cpc_bid_micros = max_cpc_bid_micros
                campaign.bidding_strategy.manual_cpc_bidding_strategy = manual
            else:
                raise ValueError(
                    "bidding_strategy must be MAXIMIZE_CLICKS, "
                    f"MAXIMIZE_CONVERSIONS or MANUAL_CPC, got {bidding_strategy}"
                )

            if conversion_rate is not None:
                campaign.conversion_rate = conversion_rate

            for negative in negative_keywords or []:
                neg = KeywordInfo()
                neg.text = negative
                neg.match_type = KeywordMatchTypeEnum.KeywordMatchType.BROAD
                campaign.negative_keywords.append(neg)

            ad_group = ForecastAdGroup()
            if bid_keywords and max_cpc_bid_micros is not None:
                ad_group.max_cpc_bid_micros = max_cpc_bid_micros
            for text in keywords:
                biddable = BiddableKeyword()
                biddable.keyword.text = text
                biddable.keyword.match_type = match_type
                if bid_keywords and max_cpc_bid_micros is not None:
                    biddable.max_cpc_bid_micros = max_cpc_bid_micros
                ad_group.biddable_keywords.append(biddable)
            campaign.ad_groups.append(ad_group)

            request = GenerateKeywordForecastMetricsRequest()
            request.customer_id = customer_id
            request.currency_code = currency_code
            request.forecast_period = DateRange(
                start_date=start_date, end_date=end_date
            )
            request.campaign = campaign

            response = self.client.generate_keyword_forecast_metrics(request=request)

            await ctx.log(
                level="info",
                message=(
                    f"Forecast generated for {len(keywords)} keywords "
                    f"({start_date} → {end_date})"
                ),
            )

            return {
                "forecast_period": {"start_date": start_date, "end_date": end_date},
                "currency_code": currency_code,
                "keyword_count": len(keywords),
                "campaign_forecast_metrics": self._format_forecast_metrics(
                    response.campaign_forecast_metrics
                ),
            }

        except GoogleAdsException as e:
            error_msg = format_ads_error(e)
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e
        except Exception as e:
            if is_resource_exhausted(e):
                await ctx.log(level="error", message=RATE_LIMIT_MSG)
                raise Exception(RATE_LIMIT_MSG) from e
            error_msg = f"Failed to generate keyword forecast metrics: {str(e)}"
            await ctx.log(level="error", message=error_msg)
            raise Exception(error_msg) from e

    def _format_historical_metrics_result(
        self, result: GenerateKeywordHistoricalMetricsResult
    ) -> Dict[str, Any]:
        """Format a historical-metrics result into a dictionary."""
        return {
            "text": result.text,
            "close_variants": list(result.close_variants),
            "keyword_metrics": self._format_metrics(result.keyword_metrics),
        }

    def _format_forecast_metrics(self, metrics: Any) -> Dict[str, Any]:
        """Format campaign forecast metrics into a dictionary.

        NOTE: proto-plus messages are FALSY when every field is at its default,
        so this must test ``is None`` — an all-zero forecast (bid below the
        auction floor) is a real answer, not a missing one.
        """
        if metrics is None:
            return {}

        return {
            "impressions": metrics.impressions,
            "clicks": metrics.clicks,
            "click_through_rate": metrics.click_through_rate,
            "average_cpc_micros": metrics.average_cpc_micros,
            "cost_micros": metrics.cost_micros,
            "conversions": metrics.conversions,
            "conversion_rate": metrics.conversion_rate,
            "average_cpa_micros": metrics.average_cpa_micros,
        }

    def _format_keyword_idea(self, idea: GenerateKeywordIdeaResult) -> Dict[str, Any]:
        """Format a keyword idea result into a dictionary."""
        result = {
            "text": idea.text,
            # Always format: proto-plus returns an all-default (falsy) message
            # for a zero-volume keyword, and 0 searches is a real answer.
            "keyword_idea_metrics": self._format_metrics(idea.keyword_idea_metrics),
        }

        # Add keyword annotations if available
        if idea.keyword_annotations:
            result["keyword_annotations"] = {
                "concepts": [
                    {
                        "name": concept.name,
                        "concept_group": {
                            "name": concept.concept_group.name,
                            "type": concept.concept_group.type_.name
                            if concept.concept_group.type_
                            else None,
                        }
                        if concept.concept_group
                        else None,
                    }
                    for concept in idea.keyword_annotations.concepts
                ]
            }

        return result

    def _format_metrics(self, metrics: Any) -> Dict[str, Any]:
        """Format keyword metrics into a dictionary.

        Tests ``is None`` rather than truthiness: an all-default proto-plus
        message is falsy, and a zero-volume keyword must report 0, not null.
        """
        if metrics is None:
            return {}

        return {
            "avg_monthly_searches": metrics.avg_monthly_searches,
            "monthly_search_volumes": [
                {
                    "year": volume.year,
                    "month": volume.month.name if volume.month else None,
                    "monthly_searches": volume.monthly_searches,
                }
                for volume in metrics.monthly_search_volumes
            ],
            "competition": metrics.competition.name if metrics.competition else None,
            "competition_index": metrics.competition_index,
            "low_top_of_page_bid_micros": metrics.low_top_of_page_bid_micros,
            "high_top_of_page_bid_micros": metrics.high_top_of_page_bid_micros,
        }


def create_keyword_plan_idea_tools(
    service: KeywordPlanIdeaService,
) -> List[Callable[..., Awaitable[Any]]]:
    """Create tool functions for the keyword plan idea service.

    This returns a list of tool functions that can be registered with FastMCP.
    This approach makes the tools testable by allowing service injection.
    """
    tools = []

    async def generate_keyword_ideas_from_keywords(
        ctx: Context,
        customer_id: str,
        keywords: List[str],
        language: str,
        geo_target_constants: List[str],
        keyword_plan_network: str = "GOOGLE_SEARCH_AND_PARTNERS",
        include_adult_keywords: bool = False,
        page_size: int = 100,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate keyword ideas from seed keywords. Returns ONE page of results.

        This API has a strict rate limit of 1 request per second. Do NOT call repeatedly in quick succession.

        Args:
            customer_id: The customer ID
            keywords: List of seed keywords to expand upon
            language: Language constant resource name (e.g., "languageConstants/1000" for English)
            geo_target_constants: List of geo target constant resource names (e.g., ["geoTargetConstants/2840"] for US)
            keyword_plan_network: Network type - UNSPECIFIED, GOOGLE_SEARCH, or GOOGLE_SEARCH_AND_PARTNERS
            include_adult_keywords: Whether to include adult keywords in results
            page_size: Number of results per page (max 10000)

        Returns:
            Dict with:
            - results: List of keyword ideas, each with text, keyword_idea_metrics (avg_monthly_searches, competition, bid estimates), keyword_annotations
            - next_page_token (optional): If present, more results are available. Pass this value as page_token in a subsequent call. Wait at least 2 seconds between calls.
        """
        # Normalize list params (MCP clients may send JSON strings)
        keywords = ensure_list(keywords)
        geo_target_constants = ensure_list(geo_target_constants)

        # Convert string enum to proper enum type
        keyword_plan_network_enum = resolve_enum(
            KeywordPlanNetworkEnum.KeywordPlanNetwork,
            keyword_plan_network,
            "keyword_plan_network",
        )

        return await service.generate_keyword_ideas_from_keywords(
            ctx=ctx,
            customer_id=customer_id,
            keywords=keywords,
            language=language,
            geo_target_constants=geo_target_constants,
            keyword_plan_network=keyword_plan_network_enum,
            include_adult_keywords=include_adult_keywords,
            page_size=page_size,
            page_token=page_token,
        )

    async def generate_keyword_ideas_from_url(
        ctx: Context,
        customer_id: str,
        page_url: str,
        language: str,
        geo_target_constants: List[str],
        keyword_plan_network: str = "GOOGLE_SEARCH_AND_PARTNERS",
        include_adult_keywords: bool = False,
        page_size: int = 100,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate keyword ideas from a specific URL/page. Returns ONE page of results.

        This API has a strict rate limit of 1 request per second. Do NOT call repeatedly in quick succession.

        Args:
            customer_id: The customer ID
            page_url: The full URL of a specific page to analyze
            language: Language constant resource name (e.g., "languageConstants/1000" for English)
            geo_target_constants: List of geo target constant resource names
            keyword_plan_network: Network type - UNSPECIFIED, GOOGLE_SEARCH, or GOOGLE_SEARCH_AND_PARTNERS
            include_adult_keywords: Whether to include adult keywords in results
            page_size: Number of results per page (max 10000)
            page_token: Token from a previous response's next_page_token to fetch the next page. Wait at least 2 seconds between calls.

        Returns:
            Dict with results list and optional next_page_token for pagination. Wait at least 2 seconds between paginated calls.
        """
        # Normalize list params (MCP clients may send JSON strings)
        geo_target_constants = ensure_list(geo_target_constants)

        # Convert string enum to proper enum type
        keyword_plan_network_enum = resolve_enum(
            KeywordPlanNetworkEnum.KeywordPlanNetwork,
            keyword_plan_network,
            "keyword_plan_network",
        )

        return await service.generate_keyword_ideas_from_url(
            ctx=ctx,
            customer_id=customer_id,
            page_url=page_url,
            language=language,
            geo_target_constants=geo_target_constants,
            keyword_plan_network=keyword_plan_network_enum,
            include_adult_keywords=include_adult_keywords,
            page_size=page_size,
            page_token=page_token,
        )

    async def generate_keyword_ideas_from_site(
        ctx: Context,
        customer_id: str,
        site_url: str,
        language: str,
        geo_target_constants: List[str],
        keyword_plan_network: str = "GOOGLE_SEARCH_AND_PARTNERS",
        include_adult_keywords: bool = False,
        page_size: int = 100,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate keyword ideas from an entire website. Returns ONE page of results.

        This API has a strict rate limit of 1 request per second. Do NOT call repeatedly in quick succession.

        Args:
            customer_id: The customer ID
            site_url: The website domain to analyze (e.g., "example.com")
            language: Language constant resource name (e.g., "languageConstants/1000" for English)
            geo_target_constants: List of geo target constant resource names
            keyword_plan_network: Network type - UNSPECIFIED, GOOGLE_SEARCH, or GOOGLE_SEARCH_AND_PARTNERS
            include_adult_keywords: Whether to include adult keywords in results
            page_size: Number of results per page (max 10000)
            page_token: Token from a previous response's next_page_token to fetch the next page. Wait at least 2 seconds between calls.

        Returns:
            Dict with results list and optional next_page_token for pagination. Wait at least 2 seconds between paginated calls.
        """
        # Normalize list params (MCP clients may send JSON strings)
        geo_target_constants = ensure_list(geo_target_constants)

        # Convert string enum to proper enum type
        keyword_plan_network_enum = resolve_enum(
            KeywordPlanNetworkEnum.KeywordPlanNetwork,
            keyword_plan_network,
            "keyword_plan_network",
        )

        return await service.generate_keyword_ideas_from_site(
            ctx=ctx,
            customer_id=customer_id,
            site_url=site_url,
            language=language,
            geo_target_constants=geo_target_constants,
            keyword_plan_network=keyword_plan_network_enum,
            include_adult_keywords=include_adult_keywords,
            page_size=page_size,
            page_token=page_token,
        )

    async def generate_keyword_ideas_from_keywords_and_url(
        ctx: Context,
        customer_id: str,
        keywords: List[str],
        page_url: str,
        language: str,
        geo_target_constants: List[str],
        keyword_plan_network: str = "GOOGLE_SEARCH_AND_PARTNERS",
        include_adult_keywords: bool = False,
        page_size: int = 100,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate keyword ideas from both keywords and a URL. Returns ONE page of results.

        This API has a strict rate limit of 1 request per second. Do NOT call repeatedly in quick succession.

        Args:
            customer_id: The customer ID
            keywords: List of seed keywords
            page_url: The URL to analyze in combination with keywords
            language: Language constant resource name (e.g., "languageConstants/1000" for English)
            geo_target_constants: List of geo target constant resource names
            keyword_plan_network: Network type - UNSPECIFIED, GOOGLE_SEARCH, or GOOGLE_SEARCH_AND_PARTNERS
            include_adult_keywords: Whether to include adult keywords in results
            page_size: Number of results per page (max 10000)
            page_token: Token from a previous response's next_page_token to fetch the next page. Wait at least 2 seconds between calls.

        Returns:
            Dict with results list and optional next_page_token for pagination. Wait at least 2 seconds between paginated calls.
        """
        # Normalize list params (MCP clients may send JSON strings)
        keywords = ensure_list(keywords)
        geo_target_constants = ensure_list(geo_target_constants)

        # Convert string enum to proper enum type
        keyword_plan_network_enum = resolve_enum(
            KeywordPlanNetworkEnum.KeywordPlanNetwork,
            keyword_plan_network,
            "keyword_plan_network",
        )

        return await service.generate_keyword_ideas_from_keywords_and_url(
            ctx=ctx,
            customer_id=customer_id,
            keywords=keywords,
            page_url=page_url,
            language=language,
            geo_target_constants=geo_target_constants,
            keyword_plan_network=keyword_plan_network_enum,
            include_adult_keywords=include_adult_keywords,
            page_size=page_size,
            page_token=page_token,
        )

    async def generate_keyword_historical_metrics(
        ctx: Context,
        customer_id: str,
        keywords: List[str],
        language: str,
        geo_target_constants: List[str],
        keyword_plan_network: str = "GOOGLE_SEARCH",
        include_adult_keywords: bool = False,
        aggregate_metrics: bool = False,
    ) -> Dict[str, Any]:
        """Get historical search volume for an EXPLICIT keyword list (no expansion).

        Use this to score a candidate keyword list. Unlike generate_keyword_ideas_*,
        the seeds are NOT expanded — you get metrics for exactly what you pass.
        This API has a strict rate limit of 1 request per second.

        Args:
            customer_id: The customer ID
            keywords: The exact keywords to look up (max 10,000)
            language: Language constant resource name (e.g., "languageConstants/1000")
            geo_target_constants: Geo target constant resource names (e.g., ["geoTargetConstants/2840"])
            keyword_plan_network: GOOGLE_SEARCH or GOOGLE_SEARCH_AND_PARTNERS
            include_adult_keywords: Whether to include adult keywords
            aggregate_metrics: Roll close-variant volume into the keyword's metrics

        Returns:
            Dict with results: [{text, close_variants, keyword_metrics}]
        """
        keywords = ensure_list(keywords)
        geo_target_constants = ensure_list(geo_target_constants)

        keyword_plan_network_enum = resolve_enum(
            KeywordPlanNetworkEnum.KeywordPlanNetwork,
            keyword_plan_network,
            "keyword_plan_network",
        )

        return await service.generate_keyword_historical_metrics(
            ctx=ctx,
            customer_id=customer_id,
            keywords=keywords,
            language=language,
            geo_target_constants=geo_target_constants,
            keyword_plan_network=keyword_plan_network_enum,
            include_adult_keywords=include_adult_keywords,
            aggregate_metrics=aggregate_metrics,
        )

    async def generate_keyword_forecast_metrics(
        ctx: Context,
        customer_id: str,
        keywords: List[str],
        currency_code: str,
        start_date: str,
        end_date: str,
        language_constants: List[str],
        geo_target_constants: List[str],
        bidding_strategy: str = "MAXIMIZE_CLICKS",
        daily_budget_micros: Optional[int] = None,
        max_cpc_bid_micros: Optional[int] = None,
        match_type: str = "PHRASE",
        keyword_plan_network: str = "GOOGLE_SEARCH",
        negative_keywords: Optional[List[str]] = None,
        conversion_rate: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Forecast impressions/clicks/cost/CTR/avg-CPC for a keyword set at a daily budget.

        READ-ONLY — creates no campaign and spends no money. This is the v23
        replacement for the removed KeywordPlanService.GenerateForecastMetrics
        (v23 KeywordPlanService only exposes mutate_keyword_plans).
        Rate limit: 1 request per second.

        Args:
            customer_id: The customer ID
            keywords: Keywords to forecast
            currency_code: Three-letter currency code (e.g., "USD")
            start_date: Forecast start, "YYYY-MM-DD" — must be in the FUTURE
            end_date: Forecast end, "YYYY-MM-DD"
            language_constants: Language constant resource names (e.g., ["languageConstants/1000"])
            geo_target_constants: Geo target constant resource names (e.g., ["geoTargetConstants/2840"])
            bidding_strategy: MAXIMIZE_CLICKS, MAXIMIZE_CONVERSIONS or MANUAL_CPC
            daily_budget_micros: Daily budget in micros (USD × 1,000,000; $15/day = 15000000)
            max_cpc_bid_micros: Max CPC bid in micros. MANUAL_CPC -> keyword bid;
                MAXIMIZE_CLICKS -> bid ceiling; ignored for MAXIMIZE_CONVERSIONS
            match_type: EXACT, PHRASE or BROAD — applied to every keyword
            keyword_plan_network: GOOGLE_SEARCH or GOOGLE_SEARCH_AND_PARTNERS
            negative_keywords: Campaign-level negative keywords
            conversion_rate: Assumed conversion rate 0-1 to derive conversions/CPA

        Returns:
            Dict with campaign_forecast_metrics: impressions, clicks, cost_micros,
            click_through_rate, average_cpc_micros, conversions, average_cpa_micros
        """
        keywords = ensure_list(keywords)
        language_constants = ensure_list(language_constants)
        geo_target_constants = ensure_list(geo_target_constants)
        if negative_keywords is not None:
            negative_keywords = ensure_list(negative_keywords)

        match_type_enum = resolve_enum(
            KeywordMatchTypeEnum.KeywordMatchType, match_type, "match_type"
        )
        keyword_plan_network_enum = resolve_enum(
            KeywordPlanNetworkEnum.KeywordPlanNetwork,
            keyword_plan_network,
            "keyword_plan_network",
        )

        return await service.generate_keyword_forecast_metrics(
            ctx=ctx,
            customer_id=customer_id,
            keywords=keywords,
            currency_code=currency_code,
            start_date=start_date,
            end_date=end_date,
            language_constants=language_constants,
            geo_target_constants=geo_target_constants,
            bidding_strategy=bidding_strategy,
            daily_budget_micros=daily_budget_micros,
            max_cpc_bid_micros=max_cpc_bid_micros,
            match_type=match_type_enum,
            keyword_plan_network=keyword_plan_network_enum,
            negative_keywords=negative_keywords,
            conversion_rate=conversion_rate,
        )

    tools.extend(
        [
            generate_keyword_ideas_from_keywords,
            generate_keyword_ideas_from_url,
            generate_keyword_ideas_from_site,
            generate_keyword_ideas_from_keywords_and_url,
            generate_keyword_historical_metrics,
            generate_keyword_forecast_metrics,
        ]
    )
    return tools


def register_keyword_plan_idea_tools(mcp: FastMCP[Any]) -> KeywordPlanIdeaService:
    """Register keyword plan idea tools with the MCP server.

    Returns the KeywordPlanIdeaService instance for testing purposes.
    """
    service = KeywordPlanIdeaService()
    tools = create_keyword_plan_idea_tools(service)

    # Register each tool
    for tool in tools:
        mcp.tool(tool)

    return service
