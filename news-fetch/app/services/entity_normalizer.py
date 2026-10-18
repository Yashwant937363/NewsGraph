import logging
import re
from typing import Dict, List, Optional, Tuple

from app.models.documents.alias_cache import EntityAliasDocument

logger = logging.getLogger("news_pipeline.normalizer")

# Curated base normalization dictionary: {lowercase_alias: (canonical_name, default_type)}
BASE_NORMALIZATION_MAP: Dict[str, Tuple[str, str]] = {
    # Countries
    "us": ("United States", "Country"),
    "u.s.": ("United States", "Country"),
    "usa": ("United States", "Country"),
    "u.s.a.": ("United States", "Country"),
    "united states": ("United States", "Country"),
    "united states of america": ("United States", "Country"),
    "america": ("United States", "Country"),
    "uk": ("United Kingdom", "Country"),
    "u.k.": ("United Kingdom", "Country"),
    "britain": ("United Kingdom", "Country"),
    "great britain": ("United Kingdom", "Country"),
    "united kingdom": ("United Kingdom", "Country"),
    "uae": ("United Arab Emirates", "Country"),
    "u.a.e.": ("United Arab Emirates", "Country"),
    "united arab emirates": ("United Arab Emirates", "Country"),
    "russia": ("Russia", "Country"),
    "russian federation": ("Russia", "Country"),
    "china": ("China", "Country"),
    "prc": ("China", "Country"),
    "taiwan": ("Taiwan", "Country"),
    "ukraine": ("Ukraine", "Country"),
    "israel": ("Israel", "Country"),
    "iran": ("Iran", "Country"),
    "lebanon": ("Lebanon", "Country"),
    "syria": ("Syria", "Country"),
    "gaza": ("Palestine", "Country"),
    "palestine": ("Palestine", "Country"),
    "yemen": ("Yemen", "Country"),
    "saudi arabia": ("Saudi Arabia", "Country"),
    "india": ("India", "Country"),
    "pakistan": ("Pakistan", "Country"),
    "japan": ("Japan", "Country"),
    "south korea": ("South Korea", "Country"),
    "north korea": ("North Korea", "Country"),
    "germany": ("Germany", "Country"),
    "france": ("France", "Country"),
    "canada": ("Canada", "Country"),
    "australia": ("Australia", "Country"),

    # Organizations
    "eu": ("European Union", "Organization"),
    "european union": ("European Union", "Organization"),
    "un": ("United Nations", "Organization"),
    "united nations": ("United Nations", "Organization"),
    "nato": ("NATO", "Organization"),
    "who": ("World Health Organization", "Organization"),
    "world health organization": ("World Health Organization", "Organization"),
    "imf": ("International Monetary Fund", "Organization"),
    "international monetary fund": ("International Monetary Fund", "Organization"),
    "world bank": ("World Bank", "Organization"),
    "iaea": ("IAEA", "Organization"),
    "icc": ("ICC", "Organization"),
    "icj": ("ICJ", "Organization"),
    "opec": ("OPEC", "Organization"),
    "hezbollah": ("Hezbollah", "Organization"),
    "hamas": ("Hamas", "Organization"),
    "houthi": ("Houthis", "Organization"),
    "houthis": ("Houthis", "Organization"),
    "idf": ("Israel Defense Forces", "Organization"),
    "pentagon": ("The Pentagon", "Organization"),

    # People
    "biden": ("Joe Biden", "Person"),
    "joe biden": ("Joe Biden", "Person"),
    "president biden": ("Joe Biden", "Person"),
    "trump": ("Donald Trump", "Person"),
    "donald trump": ("Donald Trump", "Person"),
    "harris": ("Kamala Harris", "Person"),
    "kamala harris": ("Kamala Harris", "Person"),
    "putin": ("Vladimir Putin", "Person"),
    "vladimir putin": ("Vladimir Putin", "Person"),
    "zelensky": ("Volodymyr Zelensky", "Person"),
    "zelenskyy": ("Volodymyr Zelensky", "Person"),
    "volodymyr zelensky": ("Volodymyr Zelensky", "Person"),
    "netanyahu": ("Benjamin Netanyahu", "Person"),
    "benjamin netanyahu": ("Benjamin Netanyahu", "Person"),
    "xi": ("Xi Jinping", "Person"),
    "xi jinping": ("Xi Jinping", "Person"),
    "modi": ("Narendra Modi", "Person"),
    "narendra modi": ("Narendra Modi", "Person"),
    "macron": ("Emmanuel Macron", "Person"),
    "emmanuel macron": ("Emmanuel Macron", "Person"),
    "starmer": ("Keir Starmer", "Person"),
    "keir starmer": ("Keir Starmer", "Person"),
    "sunak": ("Rishi Sunak", "Person"),
    "rishi sunak": ("Rishi Sunak", "Person"),
    "powell": ("Jerome Powell", "Person"),
    "jerome powell": ("Jerome Powell", "Person"),
    "musk": ("Elon Musk", "Person"),
    "elon musk": ("Elon Musk", "Person"),
    "altman": ("Sam Altman", "Person"),
    "sam altman": ("Sam Altman", "Person"),
    "huang": ("Jensen Huang", "Person"),
    "jensen huang": ("Jensen Huang", "Person"),

    # Companies
    "tsmc": ("TSMC", "Company"),
    "taiwan semiconductor manufacturing company": ("TSMC", "Company"),
    "nvidia": ("Nvidia", "Company"),
    "openai": ("OpenAI", "Company"),
    "microsoft": ("Microsoft", "Company"),
    "apple": ("Apple", "Company"),
    "google": ("Google", "Company"),
    "alphabet": ("Google", "Company"),
    "amazon": ("Amazon", "Company"),
    "meta": ("Meta", "Company"),
    "facebook": ("Meta", "Company"),
    "tesla": ("Tesla", "Company"),
    "intel": ("Intel", "Company"),
    "asml": ("ASML", "Company"),
    "boeing": ("Boeing", "Company"),
    "airbus": ("Airbus", "Company"),
    "saudi aramco": ("Saudi Aramco", "Company"),
    "aramco": ("Saudi Aramco", "Company"),

    # Commodities
    "crude oil": ("Crude Oil", "Commodity"),
    "oil": ("Crude Oil", "Commodity"),
    "brent": ("Crude Oil", "Commodity"),
    "brent crude": ("Crude Oil", "Commodity"),
    "wti": ("Crude Oil", "Commodity"),
    "natural gas": ("Natural Gas", "Commodity"),
    "gas": ("Natural Gas", "Commodity"),
    "lng": ("Natural Gas", "Commodity"),
    "gold": ("Gold", "Commodity"),
    "wheat": ("Wheat", "Commodity"),
    "semiconductors": ("Semiconductors", "Commodity"),
    "chips": ("Semiconductors", "Commodity"),
    "uranium": ("Uranium", "Commodity"),
    "lithium": ("Lithium", "Commodity"),
    "copper": ("Copper", "Commodity"),

    # Industries
    "semiconductor": ("Semiconductors", "Industry"),
    "semiconductors": ("Semiconductors", "Industry"),
    "chipmaking": ("Semiconductors", "Industry"),
    "aviation": ("Aviation", "Industry"),
    "aerospace": ("Aviation", "Industry"),
    "airlines": ("Aviation", "Industry"),
    "energy": ("Energy", "Industry"),
    "defense": ("Defense", "Industry"),
    "military": ("Defense", "Industry"),
    "banking": ("Banking", "Industry"),
    "finance": ("Banking", "Industry"),
    "automotive": ("Automotive", "Industry"),
    "artificial intelligence": ("Artificial Intelligence", "Industry"),
    "ai": ("Artificial Intelligence", "Industry"),
    "pharmaceuticals": ("Pharmaceuticals", "Industry"),
    "shipping": ("Maritime Shipping", "Industry"),
}


class EntityNormalizer:
    """
    Normalizes raw entity names into canonical representations with alias tracking
    and persistent MongoDB caching.
    """

    def __init__(self):
        self._memory_cache: Dict[str, Tuple[str, str, List[str]]] = {}
        # Prepopulate memory cache from BASE_NORMALIZATION_MAP
        for key, (canon, etype) in BASE_NORMALIZATION_MAP.items():
            self._memory_cache[key] = (canon, etype, [key])

    @staticmethod
    def clean_name(raw: str) -> str:
        """Cleans and standardizes raw string input."""
        cleaned = raw.strip().strip("'\"").strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned

    async def normalize(
        self,
        raw_name: str,
        entity_type: str,
        model_aliases: Optional[List[str]] = None,
    ) -> Tuple[str, str, List[str]]:
        """
        Normalizes an entity name.
        Returns (canonical_name, verified_type, list_of_aliases).
        """
        cleaned = self.clean_name(raw_name)
        if not cleaned:
            return "", entity_type, []

        key = cleaned.lower()

        # 1. Check in-memory cache
        if key in self._memory_cache:
            canon, etype, existing_aliases = self._memory_cache[key]
            combined_aliases = set(existing_aliases)
            combined_aliases.add(cleaned)
            if model_aliases:
                for a in model_aliases:
                    c = self.clean_name(a)
                    if c:
                        combined_aliases.add(c)
            aliases_list = sorted(list(combined_aliases))
            self._memory_cache[key] = (canon, etype, aliases_list)
            return canon, etype, aliases_list

        # 2. Check MongoDB cache
        try:
            cached_doc = await EntityAliasDocument.find_one(EntityAliasDocument.raw_name == key)
            if cached_doc:
                combined_aliases = set(cached_doc.aliases)
                combined_aliases.add(cleaned)
                if model_aliases:
                    for a in model_aliases:
                        c = self.clean_name(a)
                        if c:
                            combined_aliases.add(c)
                aliases_list = sorted(list(combined_aliases))
                self._memory_cache[key] = (cached_doc.canonical_name, cached_doc.entity_type, aliases_list)
                return cached_doc.canonical_name, cached_doc.entity_type, aliases_list
        except Exception as e:
            logger.debug(f"MongoDB alias cache read notice: {e}")

        # 3. New entity: canonicalize name
        # Capitalize nicely if all lower or all upper (unless short acronym)
        if cleaned.islower() or (cleaned.isupper() and len(cleaned) > 4):
            canonical = cleaned.title()
        else:
            canonical = cleaned

        # Standardize entity type casing
        type_title = entity_type.capitalize() if entity_type else "Organization"
        valid_types = {
            "Country",
            "Company",
            "Person",
            "Organization",
            "Industry",
            "Commodity",
            "Location",
        }
        if type_title not in valid_types:
            type_title = "Organization"

        aliases_set = {cleaned, canonical}
        if model_aliases:
            for a in model_aliases:
                c = self.clean_name(a)
                if c:
                    aliases_set.add(c)
        aliases_list = sorted(list(aliases_set))

        # Update in-memory cache
        self._memory_cache[key] = (canonical, type_title, aliases_list)

        # 4. Save to MongoDB cache asynchronously
        try:
            doc = EntityAliasDocument(
                raw_name=key,
                canonical_name=canonical,
                entity_type=type_title,
                aliases=aliases_list,
            )
            await doc.insert()
        except Exception:
            # Ignore unique constraint collisions if already inserted
            pass

        return canonical, type_title, aliases_list
