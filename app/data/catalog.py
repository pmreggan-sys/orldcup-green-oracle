from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TeamSupplement:
    slug: str
    name_en: str
    primary_player_zh: str
    primary_player_en: str
    newcomer: bool
    provider_aliases: tuple[str, ...] = ()


TEAM_SUPPLEMENT = {
    "阿根廷": TeamSupplement("argentina", "Argentina", "梅西", "Lionel Messi", False, ("Argentina", "ARG")),
    "西班牙": TeamSupplement("spain", "Spain", "亚马尔", "Lamine Yamal", False, ("Spain", "ESP")),
    "法国": TeamSupplement("france", "France", "姆巴佩", "Kylian Mbappe", False, ("France", "FRA")),
    "英格兰": TeamSupplement("england", "England", "凯恩", "Harry Kane", False, ("England", "ENG")),
    "巴西": TeamSupplement("brazil", "Brazil", "维尼修斯", "Vinicius Junior", False, ("Brazil", "BRA")),
    "德国": TeamSupplement("germany", "Germany", "基米希", "Joshua Kimmich", False, ("Germany", "GER")),
    "葡萄牙": TeamSupplement("portugal", "Portugal", "C罗", "Cristiano Ronaldo", False, ("Portugal", "POR")),
    "荷兰": TeamSupplement("netherlands", "Netherlands", "范迪克", "Virgil van Dijk", False, ("Netherlands", "NED", "Holland")),
    "乌拉圭": TeamSupplement("uruguay", "Uruguay", "巴尔韦德", "Federico Valverde", False, ("Uruguay", "URU")),
    "克罗地亚": TeamSupplement("croatia", "Croatia", "莫德里奇", "Luka Modric", False, ("Croatia", "CRO")),
    "摩洛哥": TeamSupplement("morocco", "Morocco", "阿什拉夫", "Achraf Hakimi", False, ("Morocco", "MAR")),
    "哥伦比亚": TeamSupplement("colombia", "Colombia", "J罗", "James Rodriguez", False, ("Colombia", "COL")),
    "日本": TeamSupplement("japan", "Japan", "久保建英", "Takefusa Kubo", False, ("Japan", "JPN")),
    "挪威": TeamSupplement("norway", "Norway", "哈兰德", "Erling Haaland", False, ("Norway", "NOR")),
    "美国": TeamSupplement("united-states", "United States", "普利西奇", "Christian Pulisic", False, ("United States", "USA", "United States of America", "US")),
    "墨西哥": TeamSupplement("mexico", "Mexico", "S·希门尼斯", "Santiago Gimenez", False, ("Mexico", "MEX")),
    "加拿大": TeamSupplement("canada", "Canada", "戴维斯", "Alphonso Davies", False, ("Canada", "CAN")),
    "瑞士": TeamSupplement("switzerland", "Switzerland", "扎卡", "Granit Xhaka", False, ("Switzerland", "SUI")),
    "韩国": TeamSupplement("south-korea", "South Korea", "孙兴慜", "Son Heung-min", False, ("South Korea", "KOR", "Korea Republic")),
    "土耳其": TeamSupplement("turkiye", "Turkiye", "居莱尔", "Arda Guler", False, ("Turkiye", "Turkey", "TUR", "Türkiye")),
    "瑞典": TeamSupplement("sweden", "Sweden", "伊萨克", "Alexander Isak", False, ("Sweden", "SWE")),
    "奥地利": TeamSupplement("austria", "Austria", "萨比策", "Marcel Sabitzer", False, ("Austria", "AUT")),
    "比利时": TeamSupplement("belgium", "Belgium", "德布劳内", "Kevin De Bruyne", False, ("Belgium", "BEL")),
    "塞内加尔": TeamSupplement("senegal", "Senegal", "马内", "Sadio Mane", False, ("Senegal", "SEN")),
    "厄瓜多尔": TeamSupplement("ecuador", "Ecuador", "凯塞多", "Moises Caicedo", False, ("Ecuador", "ECU")),
    "埃及": TeamSupplement("egypt", "Egypt", "萨拉赫", "Mohamed Salah", False, ("Egypt", "EGY")),
    "澳大利亚": TeamSupplement("australia", "Australia", "欧文", "Jackson Irvine", False, ("Australia", "AUS")),
    "苏格兰": TeamSupplement("scotland", "Scotland", "麦克托米奈", "Scott McTominay", False, ("Scotland", "SCO")),
    "捷克": TeamSupplement("czechia", "Czechia", "希克", "Patrik Schick", False, ("Czechia", "Czech Republic", "CZE")),
    "波黑": TeamSupplement("bosnia-and-herzegovina", "Bosnia and Herzegovina", "哲科", "Edin Dzeko", False, ("Bosnia and Herzegovina", "Bosnia", "BIH")),
    "卡塔尔": TeamSupplement("qatar", "Qatar", "阿菲夫", "Akram Afif", False, ("Qatar", "QAT")),
    "巴拉圭": TeamSupplement("paraguay", "Paraguay", "阿尔米隆", "Miguel Almiron", False, ("Paraguay", "PAR")),
    "科特迪瓦": TeamSupplement("ivory-coast", "Ivory Coast", "阿丁格拉", "Simon Adingra", False, ("Ivory Coast", "Cote d'Ivoire", "CIV")),
    "突尼斯": TeamSupplement("tunisia", "Tunisia", "姆萨克尼", "Youssef Msakni", False, ("Tunisia", "TUN")),
    "伊朗": TeamSupplement("iran", "Iran", "塔雷米", "Mehdi Taremi", False, ("Iran", "IRN", "IR Iran")),
    "新西兰": TeamSupplement("new-zealand", "New Zealand", "克里斯·伍德", "Chris Wood", False, ("New Zealand", "NZL")),
    "沙特": TeamSupplement("saudi-arabia", "Saudi Arabia", "多萨里", "Salem Al-Dawsari", False, ("Saudi Arabia", "KSA")),
    "阿尔及利亚": TeamSupplement("algeria", "Algeria", "马赫雷斯", "Riyad Mahrez", False, ("Algeria", "ALG")),
    "加纳": TeamSupplement("ghana", "Ghana", "库杜斯", "Mohammed Kudus", False, ("Ghana", "GHA")),
    "巴拿马": TeamSupplement("panama", "Panama", "卡拉斯基利亚", "Adalberto Carrasquilla", False, ("Panama", "PAN")),
    "伊拉克": TeamSupplement("iraq", "Iraq", "侯赛因", "Aymen Hussein", False, ("Iraq", "IRQ")),
    "乌兹别克斯坦": TeamSupplement("uzbekistan", "Uzbekistan", "肖穆罗多夫", "Eldor Shomurodov", True, ("Uzbekistan", "UZB")),
    "约旦": TeamSupplement("jordan", "Jordan", "塔马里", "Mousa Al-Taamari", True, ("Jordan", "JOR")),
    "南非": TeamSupplement("south-africa", "South Africa", "佩西·塔乌", "Percy Tau", False, ("South Africa", "RSA", "ZAF")),
    "海地": TeamSupplement("haiti", "Haiti", "纳宗", "Duckens Nazon", False, ("Haiti", "HAI")),
    "库拉索": TeamSupplement("curacao", "Curacao", "巴库纳", "Leandro Bacuna", True, ("Curacao", "CUW", "Curaçao")),
    "佛得角": TeamSupplement("cape-verde", "Cape Verde", "门德斯", "Ryan Mendes", True, ("Cape Verde", "CPV")),
    "刚果金": TeamSupplement("dr-congo", "DR Congo", "巴坎布", "Cedric Bakambu", False, ("DR Congo", "Congo DR", "COD")),
}

HOST_TEAMS = {"美国", "加拿大", "墨西哥"}

HOST_COUNTRY_BY_SLUG = {
    "united-states": "USA",
    "canada": "CAN",
    "mexico": "MEX",
}

HOST_COUNTRY_NAMES = {
    "USA": {"zh": "美国", "en": "United States"},
    "CAN": {"zh": "加拿大", "en": "Canada"},
    "MEX": {"zh": "墨西哥", "en": "Mexico"},
}

HOST_CITY_CODES = {
    "Atlanta": "USA",
    "Boston": "USA",
    "Dallas": "USA",
    "Houston": "USA",
    "Inglewood": "USA",
    "Kansas City": "USA",
    "Miami": "USA",
    "New York": "USA",
    "Philadelphia": "USA",
    "San Francisco": "USA",
    "Seattle": "USA",
    "Monterrey": "MEX",
    "Guadalajara": "MEX",
    "Mexico City": "MEX",
    "Toronto": "CAN",
    "Vancouver": "CAN",
}

HOST_CITY_LOCALIZED = {
    "Atlanta": {"zh": "亚特兰大", "en": "Atlanta"},
    "Boston": {"zh": "波士顿", "en": "Boston"},
    "Dallas": {"zh": "达拉斯", "en": "Dallas"},
    "Houston": {"zh": "休斯敦", "en": "Houston"},
    "Inglewood": {"zh": "英格尔伍德", "en": "Inglewood"},
    "Kansas City": {"zh": "堪萨斯城", "en": "Kansas City"},
    "Miami": {"zh": "迈阿密", "en": "Miami"},
    "Monterrey": {"zh": "蒙特雷", "en": "Monterrey"},
    "Guadalajara": {"zh": "瓜达拉哈拉", "en": "Guadalajara"},
    "Mexico City": {"zh": "墨西哥城", "en": "Mexico City"},
    "New York": {"zh": "纽约", "en": "New York"},
    "Philadelphia": {"zh": "费城", "en": "Philadelphia"},
    "San Francisco": {"zh": "旧金山", "en": "San Francisco"},
    "Seattle": {"zh": "西雅图", "en": "Seattle"},
    "Toronto": {"zh": "多伦多", "en": "Toronto"},
    "Vancouver": {"zh": "温哥华", "en": "Vancouver"},
}

DEFAULT_FEATURED_TEAM_SLUGS = (
    "mexico",
    "brazil",
    "netherlands",
    "spain",
    "france",
    "argentina",
    "portugal",
    "england",
)

OFFLINE_PREVIEW_FIXTURES = (
    {
        "fixture_id": "preview-1",
        "provider_match_id": 9001,
        "team_a": "mexico",
        "team_b": "south-africa",
        "stage": "group",
        "status": "scheduled",
        "kickoff": "2026-06-11T18:00:00+00:00",
        "venue_zh": "墨西哥城",
        "venue_en": "Mexico City",
        "group": "GROUP_A",
        "home_side": "A",
        "featured": True,
    },
    {
        "fixture_id": "preview-2",
        "provider_match_id": 9002,
        "team_a": "south-korea",
        "team_b": "czechia",
        "stage": "group",
        "status": "scheduled",
        "kickoff": "2026-06-11T21:00:00+00:00",
        "venue_zh": "蒙特雷",
        "venue_en": "Monterrey",
        "group": "GROUP_A",
        "home_side": None,
        "featured": False,
    },
    {
        "fixture_id": "preview-3",
        "provider_match_id": 9003,
        "team_a": "brazil",
        "team_b": "morocco",
        "stage": "group",
        "status": "in_progress",
        "kickoff": "2026-06-12T18:00:00+00:00",
        "venue_zh": "休斯敦",
        "venue_en": "Houston",
        "group": "GROUP_C",
        "home_side": None,
        "featured": True,
    },
    {
        "fixture_id": "preview-4",
        "provider_match_id": 9004,
        "team_a": "france",
        "team_b": "england",
        "stage": "round_of_16",
        "status": "scheduled",
        "kickoff": "2026-06-30T19:00:00+00:00",
        "venue_zh": "纽约",
        "venue_en": "New York",
        "group": None,
        "home_side": None,
        "featured": True,
    },
    {
        "fixture_id": "preview-5",
        "provider_match_id": 9005,
        "team_a": "portugal",
        "team_b": "colombia",
        "stage": "group",
        "status": "finished",
        "kickoff": "2026-06-12T01:00:00+00:00",
        "venue_zh": "多伦多",
        "venue_en": "Toronto",
        "group": "GROUP_K",
        "home_side": None,
        "featured": True,
        "score_home": 2,
        "score_away": 1,
    },
    {
        "fixture_id": "preview-6",
        "provider_match_id": 9006,
        "team_a": "canada",
        "team_b": "bosnia-and-herzegovina",
        "stage": "group",
        "status": "finished",
        "kickoff": "2026-06-12T23:00:00+00:00",
        "venue_zh": "温哥华",
        "venue_en": "Vancouver",
        "group": "GROUP_B",
        "home_side": "A",
        "featured": False,
        "score_home": 1,
        "score_away": 1,
    },
)
