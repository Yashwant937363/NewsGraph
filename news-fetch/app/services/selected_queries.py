"""
150 unique, high-signal queries selected from Queries.md covering a broad range
of critical real-world events (geopolitics, governance, security, economy, technology,
natural disasters, health, transport, and science).
"""
from typing import List, Dict, Any

SELECTED_QUERIES: List[Dict[str, Any]] = [
    {
        "id": 1,
        "query": "\"military attack\" OR \"airstrike\" OR \"missile strike\" OR \"drone strike\""
    },
    {
        "id": 2,
        "query": "\"military offensive\" OR \"ground offensive\" OR \"military operation\" OR \"armed assault\""
    },
    {
        "id": 3,
        "query": "\"armed conflict\" OR \"fighting erupts\" OR \"clashes erupt\" OR \"hostilities\""
    },
    {
        "id": 4,
        "query": "\"ceasefire\" AND (\"agreement\" OR \"violated\" OR \"collapses\" OR \"broken\")"
    },
    {
        "id": 5,
        "query": "\"peace talks\" OR \"peace agreement\" OR \"ceasefire deal\" OR \"negotiations\""
    },
    {
        "id": 6,
        "query": "\"war crimes\" OR \"civilian casualties\" OR \"mass grave\" OR \"ethnic cleansing\""
    },
    {
        "id": 7,
        "query": "\"troops deployed\" OR \"military deployment\" OR \"reinforcements sent\" OR \"mobilization\""
    },
    {
        "id": 8,
        "query": "\"border clashes\" OR \"border dispute\" OR \"cross-border attack\" OR \"border incursion\""
    },
    {
        "id": 9,
        "query": "\"rebel group\" AND (\"attack\" OR \"seizes\" OR \"captures\" OR \"advances\")"
    },
    {
        "id": 10,
        "query": "\"coup attempt\" OR \"military coup\" OR \"junta takes power\" OR \"seizes power\""
    },
    {
        "id": 11,
        "query": "\"hostage\" OR \"kidnapping\" OR \"abduction\" OR \"captive\""
    },
    {
        "id": 12,
        "query": "\"arms shipment\" OR \"weapons transfer\" OR \"arms deal\" OR \"military aid\""
    },
    {
        "id": 13,
        "query": "\"terrorist attack\" OR \"bombing\" OR \"suicide bombing\" OR \"bomb blast\""
    },
    {
        "id": 14,
        "query": "\"explosion kills\" OR \"blast kills\" OR \"bombing kills\" OR \"explosion injures\""
    },
    {
        "id": 15,
        "query": "\"mass shooting\" OR \"gun attack\" OR \"shooting spree\" OR \"armed attack\""
    },
    {
        "id": 16,
        "query": "\"stabbing attack\" OR \"vehicle attack\" OR \"ramming attack\" OR \"knife attack\""
    },
    {
        "id": 17,
        "query": "\"hostage situation\" OR \"hostage crisis\" OR \"siege\" OR \"standoff\""
    },
    {
        "id": 18,
        "query": "\"security forces\" AND (\"raid\" OR \"crackdown\" OR \"operation\")"
    },
    {
        "id": 19,
        "query": "\"assassination\" OR \"assassination attempt\" OR \"targeted killing\""
    },
    {
        "id": 20,
        "query": "\"militants\" AND (\"attack\" OR \"storm\" OR \"seize\" OR \"ambush\")"
    },
    {
        "id": 21,
        "query": "\"diplomatic talks\" OR \"diplomatic breakthrough\" OR \"diplomatic row\" OR \"diplomatic crisis\""
    },
    {
        "id": 22,
        "query": "\"sanctions imposed\" OR \"new sanctions\" OR \"sanctions lifted\" OR \"sanctions eased\""
    },
    {
        "id": 23,
        "query": "\"ambassador summoned\" OR \"diplomat expelled\" OR \"expels diplomats\" OR \"recalls ambassador\""
    },
    {
        "id": 24,
        "query": "\"treaty signed\" OR \"agreement signed\" OR \"accord reached\" OR \"deal signed\""
    },
    {
        "id": 25,
        "query": "\"summit meeting\" OR \"leaders meet\" OR \"bilateral talks\" OR \"emergency summit\""
    },
    {
        "id": 26,
        "query": "\"United Nations\" AND (\"resolution\" OR \"condemns\" OR \"emergency session\" OR \"peacekeeping\")"
    },
    {
        "id": 27,
        "query": "\"international court\" OR \"ICJ ruling\" OR \"ICC investigation\" OR \"war crimes tribunal\""
    },
    {
        "id": 28,
        "query": "\"humanitarian corridor\" OR \"aid convoy\" OR \"humanitarian pause\" OR \"relief operation\""
    },
    {
        "id": 29,
        "query": "\"peacekeeping mission\" OR \"peacekeepers deployed\" OR \"peacekeepers attacked\" OR \"peacekeepers withdraw\""
    },
    {
        "id": 30,
        "query": "\"nuclear talks\" OR \"nuclear deal\" OR \"nuclear program\" OR \"atomic agency\""
    },
    {
        "id": 31,
        "query": "\"election results\" OR \"election victory\" OR \"election upset\" OR \"election fraud\""
    },
    {
        "id": 32,
        "query": "\"president elected\" OR \"prime minister elected\" OR \"new government\" OR \"sworn in\""
    },
    {
        "id": 33,
        "query": "\"coalition government\" OR \"government formed\" OR \"hung parliament\" OR \"power-sharing\""
    },
    {
        "id": 34,
        "query": "\"vote of no confidence\" OR \"government collapses\" OR \"coalition collapses\" OR \"government falls\""
    },
    {
        "id": 35,
        "query": "\"president resigns\" OR \"prime minister resigns\" OR \"government resigns\" OR \"steps down\""
    },
    {
        "id": 36,
        "query": "\"constitutional crisis\" OR \"parliament dissolved\" OR \"snap election\" OR \"power vacuum\""
    },
    {
        "id": 37,
        "query": "\"referendum\" AND (\"result\" OR \"passed\" OR \"rejected\" OR \"approved\")"
    },
    {
        "id": 38,
        "query": "\"political scandal\" OR \"corruption charges\" OR \"minister arrested\" OR \"bribery probe\""
    },
    {
        "id": 39,
        "query": "\"opposition leader\" AND (\"arrested\" OR \"detained\" OR \"charged\" OR \"disqualified\")"
    },
    {
        "id": 40,
        "query": "\"law passed\" OR \"bill approved\" OR \"policy announced\" OR \"reform approved\""
    },
    {
        "id": 41,
        "query": "\"emergency powers\" OR \"martial law\" OR \"state of emergency\" OR \"curfew imposed\""
    },
    {
        "id": 42,
        "query": "\"separatist\" OR \"independence referendum\" OR \"secession\" OR \"autonomy deal\""
    },
    {
        "id": 43,
        "query": "\"mass protests\" OR \"anti-government protests\" OR \"demonstrations\" OR \"protest march\""
    },
    {
        "id": 44,
        "query": "\"general strike\" OR \"nationwide strike\" OR \"workers strike\" OR \"labor strike\""
    },
    {
        "id": 45,
        "query": "\"riots\" OR \"violent protests\" OR \"civil unrest\" OR \"unrest spreads\""
    },
    {
        "id": 46,
        "query": "\"police crackdown\" OR \"protesters killed\" OR \"tear gas\" OR \"live rounds\""
    },
    {
        "id": 47,
        "query": "\"internet shutdown\" OR \"communications blackout\" OR \"media crackdown\" OR \"journalists detained\""
    },
    {
        "id": 48,
        "query": "\"political prisoner\" OR \"dissident arrested\" OR \"activist detained\" OR \"human rights crackdown\""
    },
    {
        "id": 49,
        "query": "\"central bank\" AND (\"raises rates\" OR \"cuts rates\" OR \"holds rates\" OR \"emergency meeting\")"
    },
    {
        "id": 50,
        "query": "\"interest rate hike\" OR \"interest rate cut\" OR \"monetary policy\" OR \"rate decision\""
    },
    {
        "id": 51,
        "query": "\"inflation\" AND (\"surges\" OR \"rises\" OR \"falls\" OR \"accelerates\")"
    },
    {
        "id": 52,
        "query": "\"GDP\" AND (\"shrinks\" OR \"grows\" OR \"contracts\" OR \"slumps\")"
    },
    {
        "id": 53,
        "query": "\"currency plunges\" OR \"currency collapses\" OR \"devaluation\" OR \"currency crisis\""
    },
    {
        "id": 54,
        "query": "\"financial crisis\" OR \"bank collapse\" OR \"bank run\" OR \"banking crisis\""
    },
    {
        "id": 55,
        "query": "\"bailout\" OR \"emergency loan\" OR \"IMF program\" OR \"rescue package\""
    },
    {
        "id": 56,
        "query": "\"sovereign default\" OR \"debt default\" OR \"missed payment\" OR \"debt crisis\""
    },
    {
        "id": 57,
        "query": "\"stock market\" AND (\"crashes\" OR \"plunges\" OR \"rallies\" OR \"sell-off\")"
    },
    {
        "id": 58,
        "query": "\"bond yields\" AND (\"spike\" OR \"surge\" OR \"jump\") OR \"bond market turmoil\""
    },
    {
        "id": 59,
        "query": "\"trade deal\" OR \"trade agreement\" OR \"tariffs imposed\" OR \"trade war\""
    },
    {
        "id": 60,
        "query": "\"export ban\" OR \"import ban\" OR \"trade restrictions\" OR \"supply chain disruption\""
    },
    {
        "id": 61,
        "query": "\"oil prices\" AND (\"surge\" OR \"plunge\" OR \"spike\") OR \"gas prices\""
    },
    {
        "id": 62,
        "query": "\"OPEC\" AND (\"cuts production\" OR \"raises production\" OR \"emergency meeting\") OR \"energy crisis\""
    },
    {
        "id": 63,
        "query": "\"company acquired\" OR \"acquisition announced\" OR \"merger approved\" OR \"takeover\""
    },
    {
        "id": 64,
        "query": "\"hostile takeover\" OR \"takeover bid\" OR \"buyout\" OR \"stake sale\""
    },
    {
        "id": 65,
        "query": "\"bankruptcy\" OR \"files for bankruptcy\" OR \"insolvency\" OR \"liquidation\""
    },
    {
        "id": 66,
        "query": "\"major layoffs\" OR \"job cuts\" OR \"workforce reduction\" OR \"hiring freeze\""
    },
    {
        "id": 67,
        "query": "\"CEO resigns\" OR \"CEO steps down\" OR \"executive resigns\" OR \"board shakeup\""
    },
    {
        "id": 68,
        "query": "\"lawsuit\" AND (\"filed\" OR \"settled\" OR \"verdict\") OR \"class action\""
    },
    {
        "id": 69,
        "query": "\"regulator\" AND (\"fines\" OR \"investigates\" OR \"blocks\" OR \"approves\")"
    },
    {
        "id": 70,
        "query": "\"antitrust\" OR \"monopoly probe\" OR \"competition investigation\" OR \"market abuse\""
    },
    {
        "id": 71,
        "query": "\"IPO\" OR \"stock listing\" OR \"goes public\" OR \"shares debut\""
    },
    {
        "id": 72,
        "query": "\"factory shutdown\" OR \"plant closure\" OR \"production halted\" OR \"operations suspended\""
    },
    {
        "id": 73,
        "query": "\"artificial intelligence\" AND (\"breakthrough\" OR \"launches\" OR \"regulation\" OR \"ban\")"
    },
    {
        "id": 74,
        "query": "\"AI model\" OR \"large language model\" OR \"generative AI\" OR \"AI safety\""
    },
    {
        "id": 75,
        "query": "\"cyberattack\" OR \"ransomware\" OR \"data breach\" OR \"hacked\""
    },
    {
        "id": 76,
        "query": "\"security breach\" OR \"leaked data\" OR \"cyber incident\" OR \"malware attack\""
    },
    {
        "id": 77,
        "query": "\"software outage\" OR \"service outage\" OR \"system failure\" OR \"cloud outage\""
    },
    {
        "id": 78,
        "query": "\"internet outage\" OR \"network disruption\" OR \"connectivity failure\" OR \"DNS outage\""
    },
    {
        "id": 79,
        "query": "\"semiconductor\" AND (\"export controls\" OR \"chip ban\" OR \"factory\" OR \"shortage\")"
    },
    {
        "id": 80,
        "query": "\"quantum computing\" AND (\"breakthrough\" OR \"milestone\" OR \"supremacy\")"
    },
    {
        "id": 81,
        "query": "\"satellite\" AND (\"launch\" OR \"failure\" OR \"debris\" OR \"collision\")"
    },
    {
        "id": 82,
        "query": "\"space mission\" OR \"rocket launch\" OR \"spacecraft landing\" OR \"spacewalk\""
    },
    {
        "id": 83,
        "query": "\"scientific discovery\" OR \"research breakthrough\" OR \"new study\" OR \"findings published\""
    },
    {
        "id": 84,
        "query": "\"clinical trial\" AND (\"results\" OR \"halted\" OR \"success\" OR \"fails\")"
    },
    {
        "id": 85,
        "query": "\"court ruling\" OR \"landmark ruling\" OR \"supreme court decision\" OR \"indicted\""
    },
    {
        "id": 86,
        "query": "\"physics breakthrough\" OR \"chemistry breakthrough\" OR \"medical breakthrough\" OR \"gene editing\""
    },
    {
        "id": 87,
        "query": "\"major earthquake\" OR \"earthquake strikes\" OR \"earthquake death toll\" OR \"earthquake damage\""
    },
    {
        "id": 88,
        "query": "\"tsunami warning\" OR \"tsunami hits\" OR \"tsunami alert\" OR \"tsunami waves\""
    },
    {
        "id": 89,
        "query": "\"flooding\" OR \"flash floods\" OR \"flood disaster\" OR \"dam overflow\""
    },
    {
        "id": 90,
        "query": "\"wildfire\" OR \"bushfire\" OR \"forest fire\" OR \"fires rage\""
    },
    {
        "id": 91,
        "query": "\"hurricane\" OR \"typhoon\" OR \"cyclone\" AND (\"hits\" OR \"makes landfall\" OR \"evacuation\")"
    },
    {
        "id": 92,
        "query": "\"volcanic eruption\" OR \"volcano erupts\" OR \"ash cloud\" OR \"lava flow\""
    },
    {
        "id": 93,
        "query": "\"landslide\" OR \"mudslide\" OR \"rockslide\" OR \"avalanche\""
    },
    {
        "id": 94,
        "query": "\"drought\" OR \"famine\" OR \"food crisis\" OR \"water shortage\""
    },
    {
        "id": 95,
        "query": "\"extreme heat\" OR \"heatwave\" OR \"record temperatures\" OR \"heat alert\""
    },
    {
        "id": 96,
        "query": "\"blizzard\" OR \"severe storm\" OR \"tornado\" OR \"cold snap\""
    },
    {
        "id": 97,
        "query": "\"disease outbreak\" OR \"virus outbreak\" OR \"epidemic\" OR \"pandemic\""
    },
    {
        "id": 98,
        "query": "\"public health emergency\" OR \"WHO declares\" OR \"health alert\" OR \"infection surge\""
    },
    {
        "id": 99,
        "query": "\"vaccine\" AND (\"approved\" OR \"rollout\" OR \"halted\" OR \"mandate\") OR \"drug approval\""
    },
    {
        "id": 100,
        "query": "\"plane crash\" OR \"train derailment\" OR \"shipwreck\" OR \"building collapse\" OR \"bridge collapse\" OR \"dam failure\""
    },
    {
        "id": 204,
        "query": "\"warship\" OR \"naval incident\" OR \"ship attacked\" OR \"tanker attacked\" OR \"maritime security\" OR \"piracy\""
    },
    {
        "id": 209,
        "query": "\"rebels capture\" OR \"insurgents seize\" OR \"armed group attack\" OR \"separatist attack\" OR \"rebel offensive\""
    },
    {
        "id": 210,
        "query": "\"missile test\" OR \"ballistic missile launch\" OR \"nuclear test\" OR \"hypersonic missile\" OR \"intercepted missile\""
    },
    {
        "id": 212,
        "query": "\"humanitarian crisis\" OR \"famine declared\" OR \"aid convoy\" OR \"civilian casualties\" OR \"humanitarian corridor\""
    },
    {
        "id": 213,
        "query": "\"refugees flee\" OR \"mass displacement\" OR \"migrant boat\" OR \"migrants drowned\" OR \"asylum seekers\" OR \"mass deportation\" OR \"extradited\""
    },
    {
        "id": 222,
        "query": "\"impeachment\" OR \"impeached\" OR \"removed from office\" OR \"ousted\" OR \"stripped of immunity\""
    },
    {
        "id": 226,
        "query": "\"parliament passes\" OR \"bill signed into law\" OR \"lawmakers approve\" OR \"government bans\" OR \"decree issued\" OR \"executive order\""
    },
    {
        "id": 232,
        "query": "\"Security Council\" OR \"UN resolution\" OR \"UN General Assembly\" OR \"UN peacekeepers\" OR \"EU leaders\" OR \"NATO announces\" OR \"African Union\" OR \"BRICS\" OR \"G20\""
    },
    {
        "id": 233,
        "query": "\"territorial dispute\" OR \"border dispute\" OR \"airspace violation\" OR \"annexation\" OR \"disputed waters\""
    },
    {
        "id": 242,
        "query": "\"crypto exchange\" OR \"bitcoin plunges\" OR \"bitcoin record\" OR \"crypto hack\" OR stablecoin"
    },
    {
        "id": 250,
        "query": "(\"IMF\" AND (bailout OR loan OR program OR approves)) OR \"World Bank approves\" OR \"debt relief\" OR \"debt restructuring\""
    },
    {
        "id": 254,
        "query": "\"found guilty\" OR convicted OR \"sentenced to\" OR acquitted OR \"life sentence\""
    },
    {
        "id": 256,
        "query": "\"money laundering\" OR \"fraud scheme\" OR \"Ponzi scheme\" OR \"drug bust\" OR \"smuggling ring\" OR \"trafficking network\""
    },
    {
        "id": 257,
        "query": "\"rare earths\" OR \"critical minerals\" OR \"export controls\" OR lithium OR \"export restrictions\""
    },
    {
        "id": 263,
        "query": "\"zero-day\" OR \"critical vulnerability\" OR \"security flaw\" OR \"state-sponsored hackers\" OR \"cyber espionage\" OR \"DDoS attack\""
    },
    {
        "id": 264,
        "query": "\"global outage\" OR \"services down\" OR \"widespread outage\" OR \"system failure\" OR \"IT outage\""
    },
    {
        "id": 266,
        "query": "\"quantum computing\" OR \"fusion energy\" OR \"humanoid robot\" OR \"battery breakthrough\" OR \"unveils new chip\" OR \"unveils new smartphone\""
    },
    {
        "id": 267,
        "query": "\"social media ban\" OR \"app banned\" OR \"internet shutdown\" OR \"internet blackout\" OR \"platform blocked\""
    },
    {
        "id": 268,
        "query": "\"electric vehicle\" AND (recall OR \"sales record\" OR plant OR \"price cut\" OR \"battery fire\")"
    },
    {
        "id": 270,
        "query": "\"space mission\" OR \"lunar mission\" OR \"Mars mission\" OR asteroid OR \"solar flare\" OR \"geomagnetic storm\""
    },
    {
        "id": 272,
        "query": "\"archaeologists discover\" OR \"fossil discovered\" OR \"new species discovered\" OR \"ancient discovery\" OR unearthed"
    },
    {
        "id": 286,
        "query": "\"ship sinks\" OR \"ferry capsizes\" OR \"boat capsizes\" OR shipwreck OR \"bridge collapse\" OR \"building collapse\""
    },
    {
        "id": 288,
        "query": "\"deadly fire\" OR \"fire breaks out\" OR blaze OR \"oil spill\" OR \"fire kills\""
    },
    {
        "id": 289,
        "query": "blackout OR \"nationwide blackout\" OR \"power grid failure\" OR \"power outage\" OR \"grid collapse\""
    },
    {
        "id": 290,
        "query": "stampede OR \"crowd crush\" OR \"festival tragedy\" OR \"stadium disaster\""
    },
    {
        "id": 291,
        "query": "\"nuclear accident\" OR \"radiation leak\" OR \"toxic spill\" OR \"chemical leak\" OR \"air pollution emergency\""
    },
    {
        "id": 292,
        "query": "\"mine collapse\" OR \"miners trapped\" OR \"mine explosion\" OR \"mining accident\""
    },
    {
        "id": 293,
        "query": "\"riots erupt\" OR looting OR \"ethnic violence\" OR \"sectarian clashes\" OR \"church attack\" OR \"mosque attack\""
    },
    {
        "id": 294,
        "query": "\"school attack\" OR \"students kidnapped\" OR \"prison riot\" OR jailbreak OR \"prison escape\""
    },
    {
        "id": 295,
        "query": "\"journalist killed\" OR \"journalist arrested\" OR \"activist jailed\" OR \"press freedom\" OR \"human rights abuses\""
    },
    {
        "id": 296,
        "query": "\"climate summit\" OR \"climate agreement\" OR \"emissions target\" OR \"climate pledge\" OR \"climate protest\""
    },
    {
        "id": 297,
        "query": "\"flights cancelled\" OR \"airport closed\" OR \"airspace closed\" OR \"flight disruption\" OR \"air traffic\""
    },
    {
        "id": 298,
        "query": "\"shipping disruption\" OR \"port closed\" OR \"canal blocked\" OR \"container shipping\" OR \"shipping lanes\""
    },
    {
        "id": 105,
        "query": "\"war declared\" OR \"declares war\" OR \"state of war\" OR \"war escalation\""
    },
    {
        "id": 114,
        "query": "\"mass shooting\" OR \"mass casualty attack\" OR \"multiple people killed\" OR \"deadly attack\""
    },
    {
        "id": 121,
        "query": "\"election overturned\" OR \"election disputed\" OR \"election challenge\" OR \"election recount\""
    },
    {
        "id": 134,
        "query": "\"diplomatic breakthrough\" OR \"diplomatic agreement\" OR \"historic agreement\" OR \"agreement reached\""
    },
    {
        "id": 144,
        "query": "\"banking crisis\" OR \"bank collapses\" OR \"bank failure\" OR \"bank rescued\""
    },
    {
        "id": 167,
        "query": "\"data breach\" OR \"data leak\" OR \"customer data exposed\" OR \"personal data stolen\""
    },
    {
        "id": 168,
        "query": "\"ransomware attack\" OR \"ransomware gang\" OR \"ransomware incident\" OR \"systems encrypted\""
    },
    {
        "id": 171,
        "query": "\"critical vulnerability\" OR \"zero-day vulnerability\" OR \"zero-day exploit\" OR \"security vulnerability exploited\""
    },
    {
        "id": 195,
        "query": "\"power grid failure\" OR \"major blackout\" OR \"nationwide blackout\" OR \"power outage\""
    },
    {
        "id": 196,
        "query": "\"oil spill\" OR \"chemical spill\" OR \"toxic leak\" OR \"industrial explosion\""
    },
    {
        "id": 197,
        "query": "\"missing aircraft\" OR \"missing ship\" OR \"rescue operation\" OR \"mass rescue\""
    },
    {
        "id": 198,
        "query": "\"death toll rises\" OR \"death toll reaches\" OR \"casualties rise\" OR \"rescue operation underway\""
    },
    {
        "id": 309,
        "query": "\"naval blockade\" OR \"warship deployed\" OR \"maritime clash\""
    },
    {
        "id": 325,
        "query": "\"political asylum granted\" OR \"extradition approved\" OR \"extradited to\""
    },
    {
        "id": 333,
        "query": "\"stock market crash\" OR \"market plummets\" OR \"trading halted\""
    },
    {
        "id": 339,
        "query": "\"merger announced\" OR \"mega merger\" OR \"merger approved\""
    },
    {
        "id": 361,
        "query": "\"cloud service outage\" OR \"undersea cable severed\" OR \"internet blackout\""
    }
]

def get_selected_queries() -> List[Dict[str, Any]]:
    """Returns the list of 150 unique query items with id and query string."""
    return list(SELECTED_QUERIES)
