"""Default runtime schema configuration for Kobie's ArcGuide fields.

The extraction engine remains generic; this module is the project-level schema
config that tells the generic extractor which fields Kobie currently cares
about.
"""

from __future__ import annotations

from functools import lru_cache

from pipeline.stages.extractor import FieldDef, ObjectTypeDef, SchemaConfig


FOCUSED_SCHEMA_FIELD_PATHS: tuple[str, ...] = (
    "program_basics.program_name",
    "program_basics.brand",
    "program_basics.industry",
    "program_basics.program_type",
    "program_basics.geography",
    "program_basics.membership_count",
    "earn_mechanics.base_earn_rate",
    "earn_mechanics.bonus_categories",
    "earn_mechanics.non_transactional_earn",
    "burn_mechanics.redemption_options",
    "burn_mechanics.redemption_thresholds",
    "burn_mechanics.point_value_cpp",
    "burn_mechanics.expiry_policy",
    "tier_system.tier_names",
    "tier_system.qualification_criteria",
    "tier_system.tier_benefits",
    "tier_system.qualification_period",
    "partnerships.partner_names",
    "partnerships.partnership_type",
    "partnerships.details",
    "digital_experience.mobile_app_available",
    "digital_experience.app_ratings",
    "digital_experience.personalization_features",
    "digital_experience.gamification_features",
    "member_sentiment.ratings",
    "member_sentiment.common_praise",
    "member_sentiment.common_complaints",
    "member_sentiment.sources_checked",
    "competitive_position.key_differentiators",
    "competitive_position.weaknesses",
    "competitive_position.closest_competitors",
)


IDENTITY_FIELD_PATHS = frozenset(
    {
        "program_basics.program_name",
        "program_basics.brand",
        "program_basics.geography",
    }
)


FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "name": ("program_basics.program_name",),
    "brand": ("program_basics.brand",),
    "industry": ("program_basics.industry",),
    "type": ("program_basics.program_type",),
    "program_type": ("program_basics.program_type",),
    "geography": ("program_basics.geography",),
    "membership_count": ("program_basics.membership_count",),
    "earn_rate_base": ("earn_mechanics.base_earn_rate",),
    "base_earn_rate": ("earn_mechanics.base_earn_rate",),
    "bonus_categories": ("earn_mechanics.bonus_categories",),
    "non_transactional_earn": ("earn_mechanics.non_transactional_earn",),
    "redemption_value": ("burn_mechanics.point_value_cpp",),
    "point_value": ("burn_mechanics.point_value_cpp",),
    "cpp": ("burn_mechanics.point_value_cpp",),
    "redemption_options": ("burn_mechanics.redemption_options",),
    "redemption_thresholds": ("burn_mechanics.redemption_thresholds",),
    "expiry_policy": ("burn_mechanics.expiry_policy",),
    "tier_structure": (
        "tier_system.tier_names",
        "tier_system.qualification_criteria",
        "tier_system.tier_benefits",
        "tier_system.qualification_period",
    ),
    "tier_names": ("tier_system.tier_names",),
    "qualification_criteria": ("tier_system.qualification_criteria",),
    "qualification_period": ("tier_system.qualification_period",),
    "tier_benefits": ("tier_system.tier_benefits",),
    "partnerships": (
        "partnerships.partner_names",
        "partnerships.partnership_type",
        "partnerships.details",
    ),
    "partner_names": ("partnerships.partner_names",),
    "partner_details": ("partnerships.details",),
    "earn_details": ("partnerships.details",),
    "burn_details": ("partnerships.details",),
    "mobile_app": ("digital_experience.mobile_app_available",),
    "app_ratings": ("digital_experience.app_ratings",),
    "app_reviews": (
        "digital_experience.app_ratings",
        "digital_experience.mobile_app_available",
    ),
    "digital_experience": (
        "digital_experience.mobile_app_available",
        "digital_experience.app_ratings",
        "digital_experience.personalization_features",
        "digital_experience.gamification_features",
    ),
    "app_store_rating": ("digital_experience.app_ratings",),
    "play_store_rating": ("digital_experience.app_ratings",),
    "personalization": ("digital_experience.personalization_features",),
    "gamification": ("digital_experience.gamification_features",),
    "member_sentiment": (
        "member_sentiment.ratings",
        "member_sentiment.common_praise",
        "member_sentiment.common_complaints",
        "member_sentiment.sources_checked",
    ),
    "ratings": ("member_sentiment.ratings",),
    "sources_checked": ("member_sentiment.sources_checked",),
    "review_sources_checked": ("member_sentiment.sources_checked",),
    "forum_sources_checked": ("member_sentiment.sources_checked",),
    "competitive_position": (
        "competitive_position.key_differentiators",
        "competitive_position.weaknesses",
        "competitive_position.closest_competitors",
    ),
    "closest_competitors": ("competitive_position.closest_competitors",),
}


@lru_cache(maxsize=1)
def default_arcguide_schema_config() -> SchemaConfig:
    """Return the focused runtime schema required for the current report."""

    fields = [
        FieldDef(
            name=field_path,
            description=_field_description(field_path),
            value_type=_value_type_for_field(field_path),
            identity=field_path in IDENTITY_FIELD_PATHS,
        )
        for field_path in FOCUSED_SCHEMA_FIELD_PATHS
    ]
    return SchemaConfig(
        object_types=[
            ObjectTypeDef(
                object_type="loyalty_intelligence",
                description=(
                    "Competitive intelligence facts extracted from explicit source text. "
                    "Fields use ArcGuide dot paths."
                ),
                fields=fields,
            )
        ]
    )


def all_default_field_paths() -> list[str]:
    """Return the focused configured field paths."""

    return list(FOCUSED_SCHEMA_FIELD_PATHS)


_FIELD_DESCRIPTIONS: dict[str, str] = {
    "program_basics.program_name": (
        "The official marketed name of the loyalty program as the operator brands it "
        "(e.g. 'Marriott Bonvoy', 'AAdvantage', 'Membership Rewards'). "
        "Do NOT extract a parent company name, hotel brand, airline name, or credit card product name."
    ),
    "program_basics.brand": (
        "The single brand or company that owns and operates the loyalty program "
        "(e.g. 'Marriott', 'American Airlines', 'HDFC Bank'). "
        "Do NOT extract a program name, sub-brand, or third-party partner name."
    ),
    "program_basics.industry": (
        "The industry vertical the program operates in — one of: Hotel, Airline, "
        "Banking/Credit Card, Retail, E-Commerce, Coalition, or Other. "
        "Do NOT extract the program type or geographic market."
    ),
    "program_basics.program_type": (
        "The structural type of the program: 'points-based', 'miles-based', 'cashback', "
        "'tiered loyalty', 'coalition', etc. "
        "Do NOT extract the industry vertical or a marketing tagline."
    ),
    "program_basics.geography": (
        "The operational geographic SCOPE or FOOTPRINT of the loyalty program — "
        "e.g. 'global', 'United States and Canada', 'India', 'Southeast Asia'. "
        "Do NOT extract a specific city, a member's home location, a hotel or store address, "
        "a flight destination, or any incidental geographic mention in a review or forum post. "
        "A value like 'Dallas, US' or 'Mumbai, IN' is NEVER a valid program geography."
    ),
    "program_basics.membership_count": (
        "The total number of ENROLLED LOYALTY PROGRAM MEMBERS — individual human customers "
        "signed up for the program (e.g. '220 million members', '14 million active members'). "
        "Do NOT extract hotel property count, room count, store count, fleet size, "
        "card-in-force count, branch count, employee count, or any count that is NOT enrolled human members. "
        "If the source says 'rooms', 'properties', 'hotels', 'stores', or 'branches', it is NOT the membership count."
    ),
    "earn_mechanics.base_earn_rate": (
        "The standard default earn rate for members with no elite status and no bonus category — "
        "e.g. '1 point per ₹100 spent', '10 points per $1 at most brands'. "
        "Do NOT extract bonus, accelerated, or category-specific earn rates. "
        "Do NOT extract financial accounting figures about points issuance or accrual."
    ),
    "earn_mechanics.bonus_categories": (
        "Specific spend categories, merchant types, or partner brands that earn points at a "
        "HIGHER rate than the base rate — e.g. 'dining: 3x points', '5 points per dollar at select brands'. "
        "Do NOT extract the base earn rate or partner-earn rates that require a separate co-brand card."
    ),
    "earn_mechanics.non_transactional_earn": (
        "Ways members can earn points WITHOUT making a purchase transaction — "
        "e.g. completing a profile, referring friends, taking surveys, using a partner app, "
        "dining program enrolment, social media actions, writing hotel reviews. "
        "Do NOT extract financial/accounting disclosures about point 'breakage', "
        "deferred revenue, redemption liability, or unredeemed points. "
        "Do NOT extract base earn rates or bonus category earn rates."
    ),
    "burn_mechanics.redemption_options": (
        "The categories of things members can redeem accumulated points/miles FOR — "
        "e.g. 'hotel stays', 'flights', 'gift cards', 'statement credit', 'merchandise', "
        "'airline transfer', 'experiences'. "
        "Do NOT extract redemption thresholds, minimum points required, or point CPP values."
    ),
    "burn_mechanics.redemption_thresholds": (
        "The minimum number of points/miles required to make any redemption, or the smallest "
        "redemption unit — e.g. 'minimum 5,000 points', 'as little as 3,500 points + $55 cash'. "
        "Do NOT extract the earn rate, point value in cents, or a general redemption category description."
    ),
    "burn_mechanics.point_value_cpp": (
        "The estimated or stated value of ONE point/mile in cents (cents-per-point / CPP) "
        "or equivalent local currency — e.g. '0.8 cents per point', '₹0.25 per point'. "
        "Extract the numeric value only, not the earn rate or redemption minimum. "
        "Preserve the currency context (USD/CAD/INR) if the source makes it explicit."
    ),
    "burn_mechanics.expiry_policy": (
        "The policy governing when accumulated POINTS expire due to MEMBER INACTIVITY — "
        "e.g. 'points expire after 24 months of no earning or redeeming activity'. "
        "Do NOT extract the elite tier status validity period, tier requalification period, "
        "or any duration referring to how long an elite STATUS remains valid rather than points. "
        "A sentence like 'status is valid for the rest of the calendar year' is NOT the expiry policy."
    ),
    "tier_system.tier_names": (
        "The COMPLETE ordered list of ALL elite status tier names — from lowest to highest — "
        "e.g. ['Silver', 'Gold', 'Platinum', 'Titanium', 'Ambassador Elite']. "
        "Extract ALL tiers visible in the source; do NOT stop at one or two tiers if more exist. "
        "Do NOT extract partner tier names or co-brand card tier names."
    ),
    "tier_system.qualification_criteria": (
        "The metric(s) used to earn or maintain elite status — e.g. 'qualifying nights per year', "
        "'qualifying flights', 'calendar year spend amount', 'tier points'. "
        "Do NOT extract numeric thresholds (those belong in tier_thresholds). "
        "Do NOT extract benefit descriptions."
    ),
    "tier_system.tier_benefits": (
        "A list of specific member benefits attached to a NAMED elite tier — "
        "e.g. room upgrades, bonus points percentage, lounge access, late checkout. "
        "Always attribute to the specific tier name mentioned in the source. "
        "Do NOT extract qualification criteria or point-earning rules."
    ),
    "tier_system.qualification_period": (
        "The time window over which qualifying activity is measured to earn or maintain elite status — "
        "e.g. 'calendar year (Jan–Dec)', 'rolling 12 months', 'membership year'. "
        "Do NOT extract point expiry periods or elite status validity duration."
    ),
    "partnerships.partner_names": (
        "A list of NAMED external partner brands the program has earn/burn/transfer arrangements with — "
        "e.g. specific airline names, hotel chains, car rental brands, credit card issuers, retail merchants. "
        "Do NOT extract the program's own sub-brands or properties. "
        "Do NOT extract generic category labels like 'airlines' or 'banks' without specific brand names."
    ),
    "partnerships.partnership_type": (
        "The category of partnership — e.g. 'airline transfer partner', 'hotel earn partner', "
        "'co-brand credit card', 'merchant earn partner', 'lifestyle partner'. "
        "Do NOT extract partner names here; those belong in partner_names."
    ),
    "partnerships.details": (
        "Specific terms, rates, or notable conditions of named partnerships — "
        "e.g. transfer ratios, earn rates at specific partners, exclusivity clauses. "
        "Do NOT extract generic program descriptions or brand lists without operational detail."
    ),
    "digital_experience.mobile_app_available": (
        "Whether the program has an official mobile app available to members — 'yes' or 'no'. "
        "Do NOT extract app ratings, feature lists, or technology strategy statements."
    ),
    "digital_experience.app_ratings": (
        "Numeric ratings from Apple App Store and/or Google Play Store — "
        "e.g. '4.8 on App Store', '4.2 on Google Play (Android)'. "
        "Only extract scores explicitly stated as app store ratings with a platform name. "
        "Do NOT extract general member satisfaction scores, survey results, or star counts from non-app-store sources."
    ),
    "digital_experience.personalization_features": (
        "Specific personalization capabilities offered to members in the app or website — "
        "e.g. 'personalized offers', 'mobile check-in', 'room preference saving', "
        "'tailored recommendations', 'chat with hotel'. "
        "Do NOT extract general technology strategy or AI investment statements."
    ),
    "digital_experience.gamification_features": (
        "Specific gamification MECHANICS available to members — "
        "e.g. 'status challenges', 'streak bonuses', 'milestone bonus points', "
        "'limited-time point multiplier events', 'badges', 'progress trackers'. "
        "Do NOT extract general AI/technology strategy statements, digital transformation language, "
        "corporate innovation messaging, or any statement that does not describe "
        "an actual consumer-facing gamification mechanic."
    ),
    "member_sentiment.ratings": (
        "Numeric member satisfaction scores from review platforms — "
        "e.g. 'Trustpilot: 3.2/5', 'Google Reviews: 4.1', 'Reddit: mostly negative'. "
        "Only extract scores explicitly attributed to a named review platform. "
        "Do NOT extract app store ratings (those belong in app_ratings)."
    ),
    "member_sentiment.common_praise": (
        "Recurring POSITIVE themes in member reviews and community discussions — "
        "e.g. 'generous elite night credits', 'easy redemption process', 'strong airline partners'. "
        "Extract only themes that appear across multiple reviews or posts, not a single compliment."
    ),
    "member_sentiment.common_complaints": (
        "Recurring NEGATIVE themes in member reviews, forums, and community discussions — "
        "e.g. 'dynamic pricing reduced award value', 'poor customer service response times'. "
        "Extract only themes visible in the source text. "
        "Do NOT fabricate or generalize from a single isolated incident."
    ),
    "member_sentiment.sources_checked": (
        "The specific review platforms, forums, or communities where member sentiment was found — "
        "e.g. ['FlyerTalk', 'Reddit r/marriott', 'Trustpilot', 'Google Reviews']. "
        "List only sources actually referenced in the chunk text."
    ),
    "competitive_position.key_differentiators": (
        "Features, policies, or strengths that make this program stand out vs. competitors — "
        "e.g. 'broadest airline transfer network', 'confirmed suite upgrades', 'no blackout dates'. "
        "Do NOT extract generic marketing language without specific substantiated claims."
    ),
    "competitive_position.weaknesses": (
        "Documented weaknesses or competitive disadvantages specific to the LOYALTY PROGRAM — "
        "e.g. 'dynamic pricing reduces redemption predictability', 'limited partner airline network'. "
        "Do NOT extract general macroeconomic risk disclosures, supply/demand language, "
        "or broad business risks that are not specific to the loyalty program."
    ),
    "competitive_position.closest_competitors": (
        "Named competing loyalty programs or brands in the same category — "
        "e.g. ['Hilton Honors', 'IHG One Rewards', 'World of Hyatt']. "
        "Use specific program names, NOT category descriptions like 'other airlines' or 'other banks'."
    ),
}


def _field_description(field_path: str) -> str:
    if field_path in _FIELD_DESCRIPTIONS:
        return _FIELD_DESCRIPTIONS[field_path]
    section, field_name = field_path.split(".", 1)
    readable = field_name.replace("_", " ")
    section_readable = section.replace("_", " ")
    return f"Explicitly stated {readable} for the {section_readable} section."


def _value_type_for_field(field_path: str) -> str:
    if field_path.endswith(("membership_count", "point_value_cpp")):
        return "number"
    if field_path.endswith(
        (
            "app_ratings",
            "bonus_categories",
            "redemption_options",
            "transfer_options",
            "tier_names",
            "tier_benefits",
            "partner_names",
            "details",
            "sources_checked",
            "discontinued_partners",
            "closest_competitors",
        )
    ):
        return "array"
    return "string"
