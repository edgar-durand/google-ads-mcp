"""Tests for KeywordPlanIdeaService."""

from typing import Any
from unittest.mock import Mock, patch

import pytest
from fastmcp import Context
from google.ads.googleads.v23.enums.types.keyword_match_type import (
    KeywordMatchTypeEnum,
)
from google.ads.googleads.v23.enums.types.keyword_plan_network import (
    KeywordPlanNetworkEnum,
)
from google.ads.googleads.v23.services.services.keyword_plan_idea_service import (
    KeywordPlanIdeaServiceClient,
)

from src.services.planning.keyword_plan_idea_service import (
    KeywordPlanIdeaService,
    register_keyword_plan_idea_tools,
)


@pytest.fixture
def keyword_plan_idea_service(mock_sdk_client: Any) -> KeywordPlanIdeaService:
    """Create a KeywordPlanIdeaService instance with mocked dependencies."""
    # Mock KeywordPlanIdeaService client
    mock_idea_client = Mock(spec=KeywordPlanIdeaServiceClient)
    mock_sdk_client.client.get_service.return_value = mock_idea_client  # type: ignore

    with patch(
        "src.services.planning.keyword_plan_idea_service.get_sdk_client",
        return_value=mock_sdk_client,
    ):
        service = KeywordPlanIdeaService()
        # Force client initialization
        _ = service.client
        return service


def create_mock_keyword_idea(
    text: str = "test keyword",
    avg_monthly_searches: int = 1000,
    competition: str = "MEDIUM",
    competition_index: int = 50,
    low_bid: int = 500000,
    high_bid: int = 1000000,
) -> Mock:
    """Create a mock keyword idea result."""
    idea = Mock()
    idea.text = text

    # Mock metrics
    idea.keyword_idea_metrics = Mock()
    idea.keyword_idea_metrics.avg_monthly_searches = avg_monthly_searches
    idea.keyword_idea_metrics.competition = Mock()
    idea.keyword_idea_metrics.competition.name = competition
    idea.keyword_idea_metrics.competition_index = competition_index
    idea.keyword_idea_metrics.low_top_of_page_bid_micros = low_bid
    idea.keyword_idea_metrics.high_top_of_page_bid_micros = high_bid

    # Mock monthly search volumes
    volume1 = Mock()
    volume1.year = 2024
    volume1.month = Mock()
    volume1.month.name = "JANUARY"
    volume1.monthly_searches = 1100

    volume2 = Mock()
    volume2.year = 2024
    volume2.month = Mock()
    volume2.month.name = "FEBRUARY"
    volume2.monthly_searches = 900

    idea.keyword_idea_metrics.monthly_search_volumes = [volume1, volume2]

    # Mock annotations
    idea.keyword_annotations = Mock()
    concept = Mock()
    concept.name = "Running"
    concept.concept_group = Mock()
    concept.concept_group.name = "Sports & Fitness"
    concept.concept_group.type_ = Mock()
    concept.concept_group.type_.name = "CATEGORY"
    idea.keyword_annotations.concepts = [concept]

    return idea


def create_mock_pager(ideas: list[Mock], next_page_token: str = "") -> Mock:
    """Create a mock pager that mimics GenerateKeywordIdeasPager."""
    first_page = Mock()
    first_page.results = ideas
    first_page.next_page_token = next_page_token

    pager = Mock()
    pager.pages = iter([first_page])
    return pager


@pytest.mark.asyncio
async def test_generate_keyword_ideas_from_keywords(
    keyword_plan_idea_service: KeywordPlanIdeaService,
    mock_sdk_client: Any,
    mock_ctx: Context,
) -> None:
    """Test generating keyword ideas from keywords."""
    # Arrange
    customer_id = "1234567890"
    keywords = ["running shoes", "athletic footwear"]
    language = "languageConstants/1000"
    geo_target_constants = ["geoTargetConstants/2840"]  # US

    # Mock response
    mock_ideas = [
        create_mock_keyword_idea(
            "running shoes sale", 5000, "HIGH", 80, 750000, 1500000
        ),
        create_mock_keyword_idea(
            "best running shoes", 3000, "MEDIUM", 60, 600000, 1200000
        ),
        create_mock_keyword_idea(
            "cheap athletic footwear", 1500, "LOW", 30, 400000, 800000
        ),
    ]

    # Get the mocked idea service client
    mock_idea_client = keyword_plan_idea_service.client  # type: ignore
    mock_idea_client.generate_keyword_ideas.return_value = create_mock_pager(mock_ideas)  # type: ignore

    # Act
    result = await keyword_plan_idea_service.generate_keyword_ideas_from_keywords(
        ctx=mock_ctx,
        customer_id=customer_id,
        keywords=keywords,
        language=language,
        geo_target_constants=geo_target_constants,
        keyword_plan_network=KeywordPlanNetworkEnum.KeywordPlanNetwork.GOOGLE_SEARCH_AND_PARTNERS,
        include_adult_keywords=False,
        page_size=100,
    )

    # Assert
    ideas = result["results"]
    assert len(ideas) == 3
    assert ideas[0]["text"] == "running shoes sale"
    assert ideas[0]["keyword_idea_metrics"]["avg_monthly_searches"] == 5000
    assert ideas[0]["keyword_idea_metrics"]["competition"] == "HIGH"
    assert ideas[0]["keyword_idea_metrics"]["competition_index"] == 80
    assert ideas[0]["keyword_idea_metrics"]["low_top_of_page_bid_micros"] == 750000
    assert ideas[0]["keyword_idea_metrics"]["high_top_of_page_bid_micros"] == 1500000
    assert len(ideas[0]["keyword_idea_metrics"]["monthly_search_volumes"]) == 2
    assert ideas[0]["keyword_annotations"]["concepts"][0]["name"] == "Running"

    # Verify the API call
    mock_idea_client.generate_keyword_ideas.assert_called_once()  # type: ignore
    call_args = mock_idea_client.generate_keyword_ideas.call_args  # type: ignore
    request = call_args[1]["request"]
    assert request.customer_id == customer_id
    assert list(request.keyword_seed.keywords) == keywords
    assert request.language == language
    assert list(request.geo_target_constants) == geo_target_constants
    assert (
        request.keyword_plan_network
        == KeywordPlanNetworkEnum.KeywordPlanNetwork.GOOGLE_SEARCH_AND_PARTNERS
    )
    assert request.include_adult_keywords is False
    assert request.page_size == 100

    # Verify logging
    mock_ctx.log.assert_called_once_with(  # type: ignore
        level="info",
        message="Generated 3 keyword ideas from 2 seed keywords",
    )


@pytest.mark.asyncio
async def test_generate_keyword_ideas_from_url(
    keyword_plan_idea_service: KeywordPlanIdeaService,
    mock_sdk_client: Any,
    mock_ctx: Context,
) -> None:
    """Test generating keyword ideas from a URL."""
    # Arrange
    customer_id = "1234567890"
    page_url = "https://example.com/running-shoes"
    language = "languageConstants/1000"
    geo_target_constants = ["geoTargetConstants/2840"]

    # Mock response
    mock_ideas = [
        create_mock_keyword_idea(
            "marathon running shoes", 2000, "MEDIUM", 55, 650000, 1300000
        ),
        create_mock_keyword_idea(
            "trail running footwear", 1200, "LOW", 35, 450000, 900000
        ),
    ]

    # Get the mocked idea service client
    mock_idea_client = keyword_plan_idea_service.client  # type: ignore
    mock_idea_client.generate_keyword_ideas.return_value = create_mock_pager(mock_ideas)  # type: ignore

    # Act
    result = await keyword_plan_idea_service.generate_keyword_ideas_from_url(
        ctx=mock_ctx,
        customer_id=customer_id,
        page_url=page_url,
        language=language,
        geo_target_constants=geo_target_constants,
        keyword_plan_network=KeywordPlanNetworkEnum.KeywordPlanNetwork.GOOGLE_SEARCH,
        include_adult_keywords=False,
        page_size=50,
    )

    # Assert
    ideas = result["results"]
    assert len(ideas) == 2
    assert ideas[0]["text"] == "marathon running shoes"
    assert ideas[1]["text"] == "trail running footwear"

    # Verify the API call
    mock_idea_client.generate_keyword_ideas.assert_called_once()  # type: ignore
    call_args = mock_idea_client.generate_keyword_ideas.call_args  # type: ignore
    request = call_args[1]["request"]
    assert request.customer_id == customer_id
    assert request.url_seed.url == page_url
    assert request.language == language
    assert (
        request.keyword_plan_network
        == KeywordPlanNetworkEnum.KeywordPlanNetwork.GOOGLE_SEARCH
    )

    # Verify logging
    mock_ctx.log.assert_called_once_with(  # type: ignore
        level="info",
        message=f"Generated 2 keyword ideas from URL: {page_url}",
    )


@pytest.mark.asyncio
async def test_generate_keyword_ideas_from_site(
    keyword_plan_idea_service: KeywordPlanIdeaService,
    mock_sdk_client: Any,
    mock_ctx: Context,
) -> None:
    """Test generating keyword ideas from a site."""
    # Arrange
    customer_id = "1234567890"
    site_url = "example.com"
    language = "languageConstants/1000"
    geo_target_constants = ["geoTargetConstants/2840"]

    # Mock response
    mock_ideas = [
        create_mock_keyword_idea(
            "sports equipment online", 8000, "HIGH", 75, 800000, 1600000
        ),
    ]

    # Get the mocked idea service client
    mock_idea_client = keyword_plan_idea_service.client  # type: ignore
    mock_idea_client.generate_keyword_ideas.return_value = create_mock_pager(mock_ideas)  # type: ignore

    # Act
    result = await keyword_plan_idea_service.generate_keyword_ideas_from_site(
        ctx=mock_ctx,
        customer_id=customer_id,
        site_url=site_url,
        language=language,
        geo_target_constants=geo_target_constants,
    )

    # Assert
    ideas = result["results"]
    assert len(ideas) == 1
    assert ideas[0]["text"] == "sports equipment online"

    # Verify the API call
    mock_idea_client.generate_keyword_ideas.assert_called_once()  # type: ignore
    call_args = mock_idea_client.generate_keyword_ideas.call_args  # type: ignore
    request = call_args[1]["request"]
    assert request.customer_id == customer_id
    assert request.site_seed.site == site_url

    # Verify logging
    mock_ctx.log.assert_called_once_with(  # type: ignore
        level="info",
        message=f"Generated 1 keyword ideas from site: {site_url}",
    )


@pytest.mark.asyncio
async def test_generate_keyword_ideas_from_keywords_and_url(
    keyword_plan_idea_service: KeywordPlanIdeaService,
    mock_sdk_client: Any,
    mock_ctx: Context,
) -> None:
    """Test generating keyword ideas from both keywords and URL."""
    # Arrange
    customer_id = "1234567890"
    keywords = ["running", "fitness"]
    page_url = "https://example.com/sports"
    language = "languageConstants/1000"
    geo_target_constants = ["geoTargetConstants/2840"]

    # Mock response
    mock_ideas = [
        create_mock_keyword_idea(
            "fitness running gear", 4500, "MEDIUM", 65, 700000, 1400000
        ),
        create_mock_keyword_idea(
            "running fitness tracker", 3500, "MEDIUM", 60, 650000, 1300000
        ),
    ]

    # Get the mocked idea service client
    mock_idea_client = keyword_plan_idea_service.client  # type: ignore
    mock_idea_client.generate_keyword_ideas.return_value = create_mock_pager(mock_ideas)  # type: ignore

    # Act
    result = (
        await keyword_plan_idea_service.generate_keyword_ideas_from_keywords_and_url(
            ctx=mock_ctx,
            customer_id=customer_id,
            keywords=keywords,
            page_url=page_url,
            language=language,
            geo_target_constants=geo_target_constants,
            include_adult_keywords=True,
            page_size=200,
        )
    )

    # Assert
    ideas = result["results"]
    assert len(ideas) == 2
    assert ideas[0]["text"] == "fitness running gear"
    assert ideas[1]["text"] == "running fitness tracker"

    # Verify the API call
    mock_idea_client.generate_keyword_ideas.assert_called_once()  # type: ignore
    call_args = mock_idea_client.generate_keyword_ideas.call_args  # type: ignore
    request = call_args[1]["request"]
    assert request.customer_id == customer_id
    assert list(request.keyword_and_url_seed.keywords) == keywords
    assert request.keyword_and_url_seed.url == page_url
    assert request.include_adult_keywords is True
    assert request.page_size == 200

    # Verify logging
    mock_ctx.log.assert_called_once_with(  # type: ignore
        level="info",
        message="Generated 2 keyword ideas from keywords and URL",
    )


@pytest.mark.asyncio
async def test_error_handling(
    keyword_plan_idea_service: KeywordPlanIdeaService,
    mock_sdk_client: Any,
    mock_ctx: Context,
    google_ads_exception: Any,
) -> None:
    """Test error handling when API call fails."""
    # Arrange
    customer_id = "1234567890"

    # Get the mocked idea service client and make it raise exception
    mock_idea_client = keyword_plan_idea_service.client  # type: ignore
    mock_idea_client.generate_keyword_ideas.side_effect = google_ads_exception  # type: ignore

    # Act & Assert
    with pytest.raises(Exception) as exc_info:
        await keyword_plan_idea_service.generate_keyword_ideas_from_keywords(
            ctx=mock_ctx,
            customer_id=customer_id,
            keywords=["test"],
            language="languageConstants/1000",
            geo_target_constants=["geoTargetConstants/2840"],
        )

    assert "Failed to generate keyword ideas" in str(exc_info.value)
    assert "Test Google Ads Exception" in str(exc_info.value)

    # Verify error logging
    mock_ctx.log.assert_called_once_with(  # type: ignore
        level="error",
        message="Failed to generate keyword ideas: Test Google Ads Exception",
    )


def test_register_keyword_plan_idea_tools() -> None:
    """Test tool registration."""
    # Arrange
    mock_mcp = Mock()

    # Act
    service = register_keyword_plan_idea_tools(mock_mcp)

    # Assert
    assert isinstance(service, KeywordPlanIdeaService)

    # Verify that tools were registered
    assert mock_mcp.tool.call_count == 6  # 6 tools registered  # type: ignore

    # Verify tool functions were passed
    registered_tools = [call[0][0] for call in mock_mcp.tool.call_args_list]  # type: ignore
    tool_names = [tool.__name__ for tool in registered_tools]

    expected_tools = [
        "generate_keyword_ideas_from_keywords",
        "generate_keyword_ideas_from_url",
        "generate_keyword_ideas_from_site",
        "generate_keyword_ideas_from_keywords_and_url",
        "generate_keyword_historical_metrics",
        "generate_keyword_forecast_metrics",
    ]

    assert set(tool_names) == set(expected_tools)


# ---------------------------------------------------------------------------
# generate_keyword_historical_metrics
# ---------------------------------------------------------------------------


def create_mock_historical_result(
    text: str = "claude code app",
    avg_monthly_searches: int = 2900,
    close_variants: list[str] | None = None,
) -> Mock:
    """Create a mock GenerateKeywordHistoricalMetricsResult."""
    result = Mock()
    result.text = text
    result.close_variants = close_variants or ["claude code apps"]
    result.keyword_metrics = Mock()
    result.keyword_metrics.avg_monthly_searches = avg_monthly_searches
    result.keyword_metrics.competition = Mock()
    result.keyword_metrics.competition.name = "LOW"
    result.keyword_metrics.competition_index = 23
    result.keyword_metrics.low_top_of_page_bid_micros = 3050000
    result.keyword_metrics.high_top_of_page_bid_micros = 6740000
    result.keyword_metrics.monthly_search_volumes = []
    return result


@pytest.mark.asyncio
async def test_generate_keyword_historical_metrics(
    keyword_plan_idea_service: KeywordPlanIdeaService,
    mock_ctx: Context,
) -> None:
    """Historical metrics returns per-keyword volume without seed expansion."""
    mock_response = Mock()
    mock_response.results = [
        create_mock_historical_result("claude code app", 2900),
        create_mock_historical_result("claude code remote", 1300),
    ]

    mock_idea_client = keyword_plan_idea_service.client  # type: ignore
    mock_idea_client.generate_keyword_historical_metrics.return_value = mock_response  # type: ignore

    result = await keyword_plan_idea_service.generate_keyword_historical_metrics(
        ctx=mock_ctx,
        customer_id="1234567890",
        keywords=["claude code app", "claude code remote"],
        language="languageConstants/1000",
        geo_target_constants=["geoTargetConstants/2840"],
    )

    assert len(result["results"]) == 2
    assert result["results"][0]["text"] == "claude code app"
    assert result["results"][0]["close_variants"] == ["claude code apps"]
    assert result["results"][0]["keyword_metrics"]["avg_monthly_searches"] == 2900
    assert result["results"][1]["keyword_metrics"]["competition"] == "LOW"

    request = mock_idea_client.generate_keyword_historical_metrics.call_args[1][  # type: ignore
        "request"
    ]
    assert request.customer_id == "1234567890"
    assert list(request.keywords) == ["claude code app", "claude code remote"]
    assert list(request.geo_target_constants) == ["geoTargetConstants/2840"]
    assert (
        request.keyword_plan_network
        == KeywordPlanNetworkEnum.KeywordPlanNetwork.GOOGLE_SEARCH
    )


@pytest.mark.asyncio
async def test_generate_keyword_historical_metrics_error(
    keyword_plan_idea_service: KeywordPlanIdeaService,
    mock_ctx: Context,
) -> None:
    """Historical metrics surfaces a readable error."""
    mock_idea_client = keyword_plan_idea_service.client  # type: ignore
    mock_idea_client.generate_keyword_historical_metrics.side_effect = Exception(  # type: ignore
        "boom"
    )

    with pytest.raises(Exception) as exc_info:
        await keyword_plan_idea_service.generate_keyword_historical_metrics(
            ctx=mock_ctx,
            customer_id="1234567890",
            keywords=["claude code app"],
            language="languageConstants/1000",
            geo_target_constants=["geoTargetConstants/2840"],
        )

    assert "Failed to generate keyword historical metrics" in str(exc_info.value)


# ---------------------------------------------------------------------------
# generate_keyword_forecast_metrics
# ---------------------------------------------------------------------------


def create_mock_forecast_response() -> Mock:
    """Create a mock GenerateKeywordForecastMetricsResponse."""
    response = Mock()
    response.campaign_forecast_metrics = Mock()
    response.campaign_forecast_metrics.impressions = 12000.0
    response.campaign_forecast_metrics.clicks = 420.0
    response.campaign_forecast_metrics.click_through_rate = 0.035
    response.campaign_forecast_metrics.average_cpc_micros = 1070000
    response.campaign_forecast_metrics.cost_micros = 450000000
    response.campaign_forecast_metrics.conversions = 21.0
    response.campaign_forecast_metrics.conversion_rate = 0.05
    response.campaign_forecast_metrics.average_cpa_micros = 21400000
    return response


@pytest.mark.asyncio
async def test_generate_keyword_forecast_metrics(
    keyword_plan_idea_service: KeywordPlanIdeaService,
    mock_ctx: Context,
) -> None:
    """Forecast builds a CampaignToForecast and returns campaign metrics."""
    mock_idea_client = keyword_plan_idea_service.client  # type: ignore
    mock_idea_client.generate_keyword_forecast_metrics.return_value = (  # type: ignore
        create_mock_forecast_response()
    )

    result = await keyword_plan_idea_service.generate_keyword_forecast_metrics(
        ctx=mock_ctx,
        customer_id="1234567890",
        keywords=["claude code app", "claude code remote"],
        currency_code="USD",
        start_date="2026-09-01",
        end_date="2026-09-30",
        language_constants=["languageConstants/1000"],
        geo_target_constants=["geoTargetConstants/2840"],
        daily_budget_micros=15_000_000,
        max_cpc_bid_micros=4_000_000,
    )

    metrics = result["campaign_forecast_metrics"]
    assert metrics["impressions"] == 12000.0
    assert metrics["clicks"] == 420.0
    assert metrics["cost_micros"] == 450000000
    assert result["keyword_count"] == 2
    assert result["currency_code"] == "USD"
    assert result["forecast_period"]["start_date"] == "2026-09-01"

    request = mock_idea_client.generate_keyword_forecast_metrics.call_args[1][  # type: ignore
        "request"
    ]
    assert request.customer_id == "1234567890"
    assert request.currency_code == "USD"
    assert request.forecast_period.start_date == "2026-09-01"
    assert request.forecast_period.end_date == "2026-09-30"

    campaign = request.campaign
    assert list(campaign.language_constants) == ["languageConstants/1000"]
    assert [g.geo_target_constant for g in campaign.geo_modifiers] == [
        "geoTargetConstants/2840"
    ]
    assert (
        campaign.bidding_strategy.maximize_clicks_bidding_strategy.daily_target_spend_micros
        == 15_000_000
    )
    assert (
        campaign.bidding_strategy.maximize_clicks_bidding_strategy.max_cpc_bid_ceiling_micros
        == 4_000_000
    )

    ad_group = campaign.ad_groups[0]
    assert [k.keyword.text for k in ad_group.biddable_keywords] == [
        "claude code app",
        "claude code remote",
    ]
    assert all(
        k.keyword.match_type == KeywordMatchTypeEnum.KeywordMatchType.PHRASE
        for k in ad_group.biddable_keywords
    )
    # Keyword/ad-group bids must NOT be sent with an automated strategy —
    # the API rejects that combination (keyword_plan_idea_error: INVALID_VALUE).
    assert ad_group.max_cpc_bid_micros == 0
    assert all(k.max_cpc_bid_micros == 0 for k in ad_group.biddable_keywords)


@pytest.mark.asyncio
async def test_generate_keyword_forecast_metrics_manual_cpc_and_negatives(
    keyword_plan_idea_service: KeywordPlanIdeaService,
    mock_ctx: Context,
) -> None:
    """MANUAL_CPC maps to daily_budget_micros and negatives are attached."""
    mock_idea_client = keyword_plan_idea_service.client  # type: ignore
    mock_idea_client.generate_keyword_forecast_metrics.return_value = (  # type: ignore
        create_mock_forecast_response()
    )

    await keyword_plan_idea_service.generate_keyword_forecast_metrics(
        ctx=mock_ctx,
        customer_id="1234567890",
        keywords=["claude code app"],
        currency_code="USD",
        start_date="2026-09-01",
        end_date="2026-09-30",
        language_constants=["languageConstants/1000"],
        geo_target_constants=["geoTargetConstants/2840"],
        bidding_strategy="MANUAL_CPC",
        daily_budget_micros=30_000_000,
        max_cpc_bid_micros=2_500_000,
        match_type=KeywordMatchTypeEnum.KeywordMatchType.EXACT,
        negative_keywords=["free", "tutorial"],
        conversion_rate=0.05,
    )

    request = mock_idea_client.generate_keyword_forecast_metrics.call_args[1][  # type: ignore
        "request"
    ]
    campaign = request.campaign
    manual = campaign.bidding_strategy.manual_cpc_bidding_strategy
    assert manual.daily_budget_micros == 30_000_000
    assert manual.max_cpc_bid_micros == 2_500_000
    # MANUAL_CPC *does* carry keyword-level bids
    assert campaign.ad_groups[0].max_cpc_bid_micros == 2_500_000
    assert campaign.ad_groups[0].biddable_keywords[0].max_cpc_bid_micros == 2_500_000
    assert [n.text for n in campaign.negative_keywords] == ["free", "tutorial"]
    assert campaign.conversion_rate == 0.05
    assert (
        campaign.ad_groups[0].biddable_keywords[0].keyword.match_type
        == KeywordMatchTypeEnum.KeywordMatchType.EXACT
    )


@pytest.mark.asyncio
async def test_generate_keyword_forecast_metrics_rejects_bad_strategy(
    keyword_plan_idea_service: KeywordPlanIdeaService,
    mock_ctx: Context,
) -> None:
    """An unknown bidding strategy is rejected with a readable error."""
    with pytest.raises(Exception) as exc_info:
        await keyword_plan_idea_service.generate_keyword_forecast_metrics(
            ctx=mock_ctx,
            customer_id="1234567890",
            keywords=["claude code app"],
            currency_code="USD",
            start_date="2026-09-01",
            end_date="2026-09-30",
            language_constants=["languageConstants/1000"],
            geo_target_constants=["geoTargetConstants/2840"],
            bidding_strategy="TARGET_ROAS",
        )

    assert "bidding_strategy must be" in str(exc_info.value)


@pytest.mark.asyncio
async def test_generate_keyword_forecast_metrics_zero_forecast_is_not_dropped(
    keyword_plan_idea_service: KeywordPlanIdeaService,
    mock_ctx: Context,
) -> None:
    """An all-zero forecast must be reported as zeros, not as an empty dict.

    proto-plus messages are falsy when every field is at its default, so a
    truthiness check would silently swallow a legitimate "your bid is below
    the auction floor" answer.
    """
    from google.ads.googleads.v23.services.types.keyword_plan_idea_service import (
        GenerateKeywordForecastMetricsResponse,
    )

    mock_idea_client = keyword_plan_idea_service.client  # type: ignore
    mock_idea_client.generate_keyword_forecast_metrics.return_value = (  # type: ignore
        GenerateKeywordForecastMetricsResponse()
    )

    result = await keyword_plan_idea_service.generate_keyword_forecast_metrics(
        ctx=mock_ctx,
        customer_id="1234567890",
        keywords=["claude code app"],
        currency_code="USD",
        start_date="2026-09-01",
        end_date="2026-09-30",
        language_constants=["languageConstants/1000"],
        geo_target_constants=["geoTargetConstants/2840"],
        daily_budget_micros=15_000_000,
    )

    metrics = result["campaign_forecast_metrics"]
    assert metrics["impressions"] == 0
    assert metrics["clicks"] == 0
    assert metrics["cost_micros"] == 0
