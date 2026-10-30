"""
Next-step guidance shown after a SACA assessment.

WHAT THIS IS
Plain-language steps for the person and the health worker: how urgently to get care, what to do while arranging it,
and what NOT to do. The steps depend on the severity AND on which danger signs were recognised.

WHAT THIS IS NOT
  * It gives NO DOSES. The medicine card is general over-the-counter information (paracetamol, ibuprofen cautions,
    no aspirin for children, ORS and zinc, test before malaria medicine, no antibiotics for colds) from NHS and WHO
    pages listed in MEDICINE_SOURCES, shown only for LOW and MEDIUM results.
  * It is general first-aid and referral advice. It is not a diagnosis or a treatment plan.
  * EVERYTHING HERE IS A DRAFT. It was written from the public sources listed in SOURCES and has NOT been reviewed
    by a clinician. The Swahili is a draft too and has NOT been checked by a native speaker.
    Do not use this for real patients until a clinician signs it off (see GUIDANCE_STATUS).

Structure: every text is a dict {"en": ..., "sw": ...}. A step list is a list of such dicts, so the English and
Swahili versions can never drift out of step with each other.
"""

GUIDANCE_STATUS = "DRAFT - not clinician reviewed - Swahili not native-checked"
GUIDANCE_VERSION = "draft-2026-10-29"

SOURCES = [
    "WHO Community First Aid Response pocket guide (cdn.who.int, cfar-pocketguide.pdf): bleeding, recovery position, bites, seizures, breathing, shock, transport.",
    "WHO fact sheet: Burns (who.int): cool with clean running water about 20 minutes, cover with a clean non-stick cloth, no ice, oil, butter or pastes.",
    "WHO fact sheet: Malaria (who.int): confirm fever with a test; untreated falciparum malaria can become severe within 24 hours; severe warning signs.",
    "WHO IMCI general danger signs: not able to drink or breastfeed, vomits everything, convulsions, lethargic or unconscious.",
    "Hesperian Health Guides, first aid for seizures: protect from injury, nothing in the mouth, recovery position, emergency help if longer than 5 minutes.",
    "WHO / MSF rehydration plans for diarrhoea: small frequent sips of ORS, keep feeding, when to refer.",
    "Tygerberg Poison Information Centre snakebite first aid: immobilise, no tourniquet, no cutting or sucking, do not run, go to a facility quickly.",
    "St John Ambulance first aid advice: severe bleeding (firm pressure, add dressings, do not remove soaked ones) and heart attack (rest, comfortable position).",
    "British Red Cross / American Red Cross: trouble breathing (sit comfortably, help with the person's own prescribed medicine).",
    "Pregnancy danger signs: vaginal bleeding, severe headache, blurred vision, convulsions, loss of consciousness, severe abdominal pain, fever (training-course summary, publisher not named: confirm against WHO maternal guidance).",
]

LEVEL_NAMES = {
    "LOW": {"en": "LOW", "sw": "CHINI"},
    "MEDIUM": {"en": "MEDIUM", "sw": "WASTANI"},
    "HIGH": {"en": "HIGH", "sw": "JUU"},
    "CRITICAL": {"en": "CRITICAL", "sw": "HATARI KUBWA"},
    "NOT_ASSESSED": {"en": "NOT ASSESSED", "sw": "HAIJATATHMINIWA"},
}


def T(en, sw):
    return {"en": en, "sw": sw}


# --------------------------------------------------------------------------
# By severity
# --------------------------------------------------------------------------
TIERS = {
    "CRITICAL": {
        "headline": T("Emergency. Get help now.", "Dharura. Pata msaada sasa hivi."),
        "timeframe": T("Go to the nearest health facility immediately. Do not wait.",
                       "Nenda kituo cha afya kilicho karibu mara moja. Usisubiri."),
        "steps": [
            T("Call for help or send someone for help right now. Use your local emergency number if you have one.",
              "Piga simu ya dharura au mtume mtu kutafuta msaada sasa hivi."),
            T("Arrange transport now. Go straight to the nearest health facility.",
              "Panga usafiri sasa. Nenda moja kwa moja kituo cha afya kilicho karibu."),
            T("Stay with the person. Do not leave them alone.",
              "Kaa na mgonjwa. Usimwache peke yake."),
            T("Do not give food or drink if the person is drowsy, confused or having fits.",
              "Usimpe chakula wala kinywaji ikiwa amelegea, amechanganyikiwa au ana degedege."),
            T("Tell the health worker all the symptoms and when each one started.",
              "Mweleze mhudumu wa afya dalili zote na wakati kila moja ilipoanza."),
        ],
    },
    "HIGH": {
        "headline": T("Urgent. See a health worker today, as soon as you can.",
                      "Haraka. Muone mhudumu wa afya leo, mapema iwezekanavyo."),
        "timeframe": T("Go to a health facility today. Do not wait to see if it gets better.",
                       "Nenda kituo cha afya leo. Usisubiri kuona kama itapungua."),
        "steps": [
            T("Arrange transport to the nearest health facility now.",
              "Panga usafiri kwenda kituo cha afya kilicho karibu sasa."),
            T("Do not travel alone if the person is weak or dizzy. Take someone with you.",
              "Usisafiri peke yako ikiwa ni dhaifu au una kizunguzungu. Nenda na mtu."),
            T("If it gets worse on the way, treat it as an emergency and get help immediately.",
              "Ikizidi njiani, ichukulie kama dharura na tafuta msaada mara moja."),
            T("Tell the health worker all the symptoms and when each one started.",
              "Mweleze mhudumu wa afya dalili zote na wakati kila moja ilipoanza."),
        ],
    },
    "MEDIUM": {
        "headline": T("See a health worker soon.", "Muone mhudumu wa afya hivi karibuni."),
        "timeframe": T("Go to a health facility within a day or two. Go sooner if it gets worse.",
                       "Nenda kituo cha afya ndani ya siku moja au mbili. Nenda mapema zaidi ikizidi."),
        "steps": [
            T("Plan to visit a health facility or clinic within a day or two.",
              "Panga kwenda kituo cha afya au kliniki ndani ya siku moja au mbili."),
            T("Tell the health worker all the symptoms, when each one started, and any medicine already taken.",
              "Mweleze mhudumu wa afya dalili zote, wakati kila moja ilipoanza, na dawa yoyote iliyokwisha tumika."),
            T("If any danger sign appears, do not wait for the visit. Go straight away.",
              "Dalili yoyote ya hatari ikitokea, usisubiri siku ya miadi. Nenda mara moja."),
        ],
    },
    "LOW": {
        "headline": T("Probably mild. Rest and watch.", "Huenda ni ndogo. Pumzika na uangalie."),
        "timeframe": T("If it lasts more than about 3 days, or gets worse, see a health worker.",
                       "Ikidumu zaidi ya siku 3 hivi, au ikizidi, muone mhudumu wa afya."),
        "steps": [
            T("You may be able to look after this at home for now.",
              "Huenda unaweza kujihudumia nyumbani kwa sasa."),
            T("See a health worker if it lasts more than about 3 days, keeps coming back, or gets worse.",
              "Muone mhudumu wa afya ikidumu zaidi ya siku 3 hivi, ikijirudia, au ikizidi."),
            T("A pharmacist can also advise on simple medicines for mild symptoms.",
              "Mfamasia pia anaweza kukushauri kuhusu dawa rahisi kwa dalili ndogo."),
        ],
    },
    "NOT_ASSESSED": {
        "headline": T("SACA could not understand this. See a health worker.",
                      "SACA haikuelewa. Muone mhudumu wa afya."),
        "timeframe": T("Please see a health worker today. SACA does not guess when it cannot read the symptoms.",
                       "Tafadhali muone mhudumu wa afya leo. SACA haikisii inaposhindwa kusoma dalili."),
        "steps": [
            T("Try again by tapping the symptom buttons or the Body Map instead of typing.",
              "Jaribu tena kwa kugusa vitufe vya dalili au Ramani ya Mwili badala ya kuandika."),
            T("If you cannot tell what is wrong, see a health worker today.",
              "Ikiwa hujui tatizo ni nini, muone mhudumu wa afya leo."),
        ],
    },
}

# Self-care by severity. For HIGH and CRITICAL there is no "home care": the first-aid topics below are what to do
# while getting help.
SELF_CARE = {
    "CRITICAL": [
        T("While you wait for help or travel, follow the first-aid steps below.",
          "Wakati unasubiri msaada au ukiwa safarini, fuata hatua za huduma ya kwanza hapa chini."),
    ],
    "HIGH": [
        T("This should not be treated at home. Follow the steps below while you get to care.",
          "Hali hii haipaswi kutibiwa nyumbani. Fuata hatua hizi hapa chini wakati unaenda kupata huduma."),
    ],
    "MEDIUM": [
        T("Rest and drink plenty of safe fluids.", "Pumzika na unywe maji safi mengi."),
        T("Eat small, light meals if you can.", "Kula milo midogo na myepesi ikiwezekana."),
        T("Watch for the danger signs below. If any appear, go straight away.",
          "Angalia dalili za hatari hapa chini. Ikitokea yoyote, nenda mara moja."),
    ],
    "LOW": [
        T("Rest and drink plenty of safe fluids.", "Pumzika na unywe maji safi mengi."),
        T("Watch the symptoms. SACA cannot be sure, so do not ignore new or worsening signs.",
          "Fuatilia dalili. SACA haiwezi kuwa na uhakika, kwa hiyo usipuuze dalili mpya au zinazozidi."),
        T("Watch for the danger signs below. If any appear, go straight away.",
          "Angalia dalili za hatari hapa chini. Ikitokea yoyote, nenda mara moja."),
    ],
    "NOT_ASSESSED": [
        T("Rest and drink safe fluids while you arrange to see a health worker.",
          "Pumzika na unywe maji safi wakati unapanga kumwona mhudumu wa afya."),
    ],
}

# Extra self-care by symptom, shown only for LOW and MEDIUM (NHS cough / common cold pages).
SYMPTOM_SELF_CARE = [
    {
        "codes": {"cough", "throat_irritation", "patches_in_throat", "phlegm", "mucoid_sputum"},
        "items": [
            T("A warm drink with lemon and honey may soothe a cough or sore throat. Never give honey to a baby under 1 year.",
              "Kinywaji cha moto chenye limau na asali kinaweza kutuliza kikohozi au koo. Kamwe usimpe mtoto chini ya mwaka 1 asali."),
            T("See a health worker if a cough lasts more than 3 weeks, or if there is blood, chest pain or trouble breathing.",
              "Muone mhudumu wa afya kikohozi kikidumu zaidi ya wiki 3, au kukiwa na damu, maumivu ya kifua au kupumua kwa shida."),
        ],
    },
    {
        "codes": {"runny_nose", "congestion", "continuous_sneezing", "sinus_pressure"},
        "items": [
            T("Steam can ease a blocked nose for adults. Never let a child breathe steam from a bowl of hot water: it can scald.",
              "Mvuke unaweza kupunguza mafua kwa watu wazima. Kamwe usimwache mtoto avute mvuke kutoka bakuli la maji ya moto: unaweza kumuunguza."),
        ],
    },
    {
        "codes": {"diarrhoea", "vomiting", "dehydration"},
        "items": [
            T("Keep eating and keep breastfeeding during diarrhoea.",
              "Endelea kula na kunyonyesha wakati wa kuhara."),
            T("Wash hands with soap after using the toilet and before preparing food.",
              "Nawa mikono kwa sabuni baada ya kutumia choo na kabla ya kuandaa chakula."),
        ],
    },
    {
        "codes": {"high_fever", "mild_fever", "chills", "shivering"},
        "items": [
            T("Wear light clothing and drink plenty of fluids. Sleep under a mosquito net.",
              "Vaa nguo nyepesi na unywe vinywaji vingi. Lala ndani ya chandarua."),
        ],
    },
]

DANGER_SIGNS = {
    "title": T("Go to a health facility straight away if any of these appear",
               "Nenda kituo cha afya mara moja ikiwa mojawapo ya haya yatatokea"),
    "items": [
        T("Trouble breathing", "Kupumua kwa shida"),
        T("Fits or convulsions", "Degedege"),
        T("Very sleepy, confused, or cannot be woken", "Usingizi mwingi, kuchanganyikiwa, au hawezi kuamshwa"),
        T("Cannot drink, or vomits everything", "Hawezi kunywa, au anatapika kila kitu"),
        T("Heavy bleeding", "Kutokwa damu nyingi"),
        T("Chest pain, or a stiff neck with fever", "Maumivu ya kifua, au shingo ngumu na homa"),
        T("In pregnancy: bleeding, severe headache, blurred vision, or fever",
          "Ukiwa mjamzito: kutokwa damu, maumivu makali ya kichwa, kuona ukungu, au homa"),
    ],
}

# --------------------------------------------------------------------------
# By danger sign (topic). Lower priority number = shown first.
# --------------------------------------------------------------------------
TOPICS = [
    {
        "id": "unconscious", "priority": 1,
        "codes": {"coma", "altered_sensorium", "lethargy", "loss_of_consciousness"},
        "title": T("Person is unconscious or very hard to wake", "Mtu amepoteza fahamu au ni vigumu kumwamsha"),
        "do": [
            T("Check breathing: look at the chest and listen for up to 10 seconds.",
              "Angalia kupumua: tazama kifua na usikilize kwa hadi sekunde 10."),
            T("If breathing normally, roll them onto their side (recovery position) and tilt the head back a little to keep the airway open.",
              "Ikiwa anapumua kawaida, mgeuze ubavuni (nafasi ya kupona) na inamisha kichwa nyuma kidogo ili njia ya hewa iwe wazi."),
            T("If not breathing normally and you are trained, start chest compressions and send someone for help.",
              "Ikiwa hapumui kawaida na umefunzwa, anza kukandamiza kifua na utume mtu kutafuta msaada."),
            T("Keep them warm and stay with them until help arrives.",
              "Mfunike apate joto na ubaki naye hadi msaada ufike."),
        ],
        "dont": [
            T("Do not give anything by mouth.", "Usimpe chochote kwa mdomo."),
            T("Do not leave them alone.", "Usimwache peke yake."),
        ],
    },
    {
        "id": "breathing", "priority": 2,
        "codes": {"breathlessness", "severe_respiratory_distress", "stridor", "cyanosis", "slow_breathing"},
        "title": T("Trouble breathing", "Kupumua kwa shida"),
        "do": [
            T("Help the person sit in the position that feels most comfortable, usually upright and leaning a little forward.",
              "Msaidie akae katika nafasi anayojisikia vizuri, kwa kawaida wima na kuegemea mbele kidogo."),
            T("Loosen tight clothing around the neck and chest. Stay calm and reassure them.",
              "Legeza nguo zilizobana shingoni na kifuani. Tulia na umtuliza."),
            T("If they have their own prescribed inhaler or breathing medicine, help them use it.",
              "Ikiwa ana kifaa chake cha kuvuta dawa au dawa ya kupumua aliyoandikiwa, msaidie kuitumia."),
            T("Get to a health facility now.", "Nenda kituo cha afya sasa."),
        ],
        "dont": [
            T("Do not make them lie flat.", "Usimlaze chali."),
            T("Do not give food or drink.", "Usimpe chakula wala kinywaji."),
        ],
    },
    {
        "id": "bleeding", "priority": 3,
        "codes": {"uncontrolled_bleeding", "significant_wound", "severe_bleeding", "retained_placenta"},
        "title": T("Heavy bleeding", "Kutokwa damu nyingi"),
        "do": [
            T("Press firmly on the wound with a clean cloth or dressing, and keep pressing.",
              "Bonyeza jeraha kwa nguvu kwa kitambaa safi au bandeji, na uendelee kubonyeza."),
            T("If blood soaks through, do not remove the cloth. Add more cloth on top and keep pressing.",
              "Damu ikipenya, usiondoe kitambaa. Ongeza kitambaa kingine juu na uendelee kubonyeza."),
            T("Raise the injured arm or leg above the level of the chest if you can.",
              "Inua mkono au mguu uliojeruhiwa juu ya kiwango cha kifua ikiwezekana."),
            T("Lay the person down and keep them warm and calm.",
              "Mlaze mtu chini, umfunike apate joto na umtuliza."),
            T("Bleeding after childbirth: call for help and arrange immediate transfer to a health facility.",
              "Kutokwa damu baada ya kujifungua: tafuta msaada na upange usafiri wa haraka kwenda kituo cha afya."),
        ],
        "dont": [
            T("Do not pull out anything stuck in the wound. Press around it instead.",
              "Usitoe kitu kilichokwama kwenye jeraha. Bonyeza pembeni yake."),
            T("Do not tie a tight band unless a trained health worker tells you to.",
              "Usifunge kamba kwa kubana sana isipokuwa mhudumu wa afya aliyefunzwa akikuambia."),
        ],
    },
    {
        "id": "convulsions", "priority": 4,
        "codes": {"convulsions", "eclampsia"},
        "title": T("Fits or convulsions", "Degedege"),
        "do": [
            T("Stay with the person. Note the time the fit started.",
              "Kaa na mtu huyo. Andika muda degedege ilipoanza."),
            T("Move hard or sharp things away and put something soft under the head.",
              "Ondoa vitu vigumu au vyenye ncha karibu naye na weka kitu laini chini ya kichwa."),
            T("Loosen tight clothing around the neck.",
              "Legeza nguo zilizobana shingoni."),
            T("When the shaking stops, roll them onto their side (recovery position) and check they are breathing.",
              "Kutetemeka kukiisha, mgeuze ubavuni (nafasi ya kupona) na uhakikishe anapumua."),
            T("Get to a health facility now. It is an emergency if the fit lasts more than 5 minutes, if another starts soon after, or in a child, a pregnant woman, or someone who is not waking up.",
              "Nenda kituo cha afya sasa. Ni dharura ikiwa degedege inazidi dakika 5, ikianza nyingine karibuni, au kwa mtoto, mjamzito, au mtu asiyeamka."),
        ],
        "dont": [
            T("Do not hold the person down.", "Usimshikilie kwa nguvu."),
            T("Do not put anything in the mouth.", "Usiweke chochote mdomoni."),
            T("Do not pour water on them or use rituals.", "Usimwagie maji wala usifanye matambiko."),
        ],
    },
    {
        "id": "snakebite", "priority": 5,
        "codes": {"snake_bite", "snake_envenomation"},
        "title": T("Snakebite", "Kuumwa na nyoka"),
        "do": [
            T("Keep the person calm and as still as possible. Moving fast spreads venom faster.",
              "Mtulize mtu na abaki ametulia iwezekanavyo. Kusogea haraka huusambaza sumu haraka zaidi."),
            T("Keep the bitten arm or leg still, for example with a splint or sling. Remove rings and watches before it swells.",
              "Weka mkono au mguu ulioumwa tuli, kwa mfano kwa kiunzi au kitambaa cha kuning'inizia. Vua pete na saa kabla haujavimba."),
            T("Get to a health facility straight away. Carry the person if you can instead of letting them walk.",
              "Nenda kituo cha afya mara moja. Mbebe mtu badala ya kumruhusu atembee ikiwezekana."),
            T("Remember what the snake looked like, but do not try to catch or kill it.",
              "Kumbuka nyoka alivyokuwa, lakini usijaribu kumkamata au kumuua."),
        ],
        "dont": [
            T("Do not cut the bite, suck it, or tie anything tight above it.",
              "Usikate mahali palipoumwa, usinyonye, wala usifunge kitu kwa kubana juu yake."),
            T("Do not use ice, herbs or traditional remedies, and do not delay going to the facility.",
              "Usitumie barafu, mitishamba wala tiba za kienyeji, na usichelewe kwenda kituo cha afya."),
        ],
    },
    {
        "id": "pregnancy", "priority": 6,
        "codes": {"pre_eclampsia", "eclampsia", "retained_placenta", "prolonged_labour", "puerperal_sepsis"},
        "title": T("Pregnancy danger signs", "Dalili za hatari wakati wa ujauzito"),
        "do": [
            T("A pregnant woman with bleeding, severe headache, blurred vision, fits, severe belly pain or fever needs a health facility now.",
              "Mjamzito mwenye kutokwa damu, maumivu makali ya kichwa, kuona ukungu, degedege, maumivu makali ya tumbo au homa anahitaji kituo cha afya sasa."),
            T("Let her lie on her left side while you arrange transport.",
              "Mlaze ubavu wa kushoto wakati unapanga usafiri."),
            T("Take her antenatal card if she has one.",
              "Chukua kadi yake ya kliniki ya wajawazito ikiwa anayo."),
        ],
        "dont": [
            T("Do not wait to see if it settles.", "Usisubiri kuona kama itaisha."),
            T("Do not give her any medicine that a health worker has not told her to take.",
              "Usimpe dawa yoyote ambayo mhudumu wa afya hajamwambia atumie."),
        ],
    },
    {
        "id": "chest_pain", "priority": 7,
        "codes": {"chest_pain", "palpitations", "fast_heart_rate", "weak_pulse", "cold_extremities"},
        "title": T("Chest pain or heart trouble", "Maumivu ya kifua au tatizo la moyo"),
        "do": [
            T("Help the person sit down and rest in a comfortable position. Keep them calm.",
              "Msaidie akae na apumzike katika nafasi nzuri. Mtulize."),
            T("Get to a health facility now. Do not let them walk far.",
              "Nenda kituo cha afya sasa. Usimruhusu atembee umbali mrefu."),
            T("If they have heart medicine prescribed to them, help them take it.",
              "Ikiwa ana dawa ya moyo aliyoandikiwa, msaidie kuitumia."),
            T("Stay with them and watch their breathing.",
              "Kaa naye na uangalie kupumua kwake."),
        ],
        "dont": [
            T("Do not make them walk or work.", "Usimfanye atembee wala afanye kazi."),
        ],
    },
    {
        "id": "stroke", "priority": 8,
        "codes": {"slurred_speech", "weakness_of_one_body_side", "weakness_in_limbs", "visual_disturbances"},
        "title": T("Possible stroke: weakness on one side or speech trouble",
                   "Huenda ni kiharusi: udhaifu upande mmoja au shida ya kuongea"),
        "do": [
            T("Get to a health facility now. Every minute counts.",
              "Nenda kituo cha afya sasa. Kila dakika ni muhimu."),
            T("Note the time the symptoms started and tell the health worker.",
              "Andika muda dalili zilipoanza na umwambie mhudumu wa afya."),
            T("Keep the person comfortable and calm.",
              "Mweke vizuri na umtuliza."),
        ],
        "dont": [
            T("Do not give food or drink. They may not swallow safely.",
              "Usimpe chakula wala kinywaji. Huenda asimeze salama."),
        ],
    },
    {
        "id": "burns", "priority": 9,
        "codes": {"burns", "necrosis"},
        "title": T("Burn", "Kuungua"),
        "do": [
            T("Cool the burn with clean running water for about 20 minutes if you can.",
              "Poza sehemu iliyoungua kwa maji safi yanayotiririka kwa takribani dakika 20 ikiwezekana."),
            T("Take off rings, watches and tight clothing near the burn. Leave anything that is stuck to the skin.",
              "Vua pete, saa na nguo zilizobana karibu na pale palipoungua. Acha chochote kilichoganda kwenye ngozi."),
            T("Cover the burn loosely with a clean, non-stick cloth. Keep the rest of the person warm.",
              "Funika sehemu iliyoungua kwa kitambaa safi kisichoganda. Mfunike mtu sehemu nyingine apate joto."),
            T("Go to a health facility now if the burn is large, deep, on the face, hands, feet or private parts, from electricity or chemicals, or if smoke was breathed in.",
              "Nenda kituo cha afya sasa ikiwa jeraha la moto ni kubwa au la kina, liko usoni, mikononi, miguuni au sehemu za siri, limesababishwa na umeme au kemikali, au ikiwa moshi ulivutwa."),
        ],
        "dont": [
            T("Do not put ice, oil, butter, toothpaste or traditional pastes on a burn.",
              "Usipake barafu, mafuta, siagi, dawa ya meno wala dawa za kienyeji kwenye jeraha la moto."),
            T("Do not burst blisters.", "Usitoboe malengelenge."),
        ],
    },
    {
        "id": "injury", "priority": 10,
        "codes": {"head_injury", "trauma", "fall", "fracture", "compound_fracture", "swelling_post_trauma", "assault"},
        "title": T("Injury", "Jeraha au ajali"),
        "do": [
            T("Keep the person still. If they have neck or back pain, or are not awake, do not move their head, neck or back.",
              "Mweke mtu tuli. Ikiwa ana maumivu ya shingo au mgongo, au hajaamka, usisogeze kichwa, shingo wala mgongo wake."),
            T("Support an injured arm or leg with a splint or sling and keep it still.",
              "Saidia mkono au mguu uliojeruhiwa kwa kiunzi au kitambaa na uwe tuli."),
            T("After a head injury, get care now if there is vomiting, drowsiness, a fit, or confusion.",
              "Baada ya jeraha la kichwa, nenda kituo cha afya sasa ikiwa kuna kutapika, usingizi mwingi, degedege au kuchanganyikiwa."),
            T("Get to a health facility. Do not delay.",
              "Nenda kituo cha afya. Usichelewe."),
        ],
        "dont": [
            T("Do not give food or drink if the person may need an operation or is drowsy.",
              "Usimpe chakula wala kinywaji ikiwa huenda akahitaji upasuaji au ana usingizi mwingi."),
        ],
    },
    {
        "id": "internal_bleeding", "priority": 11,
        "codes": {"stomach_bleeding", "blood_in_sputum", "bloody_stool", "haematuria", "coagulopathy", "purpuric_rash"},
        "title": T("Blood in vomit, stool, urine or cough", "Damu kwenye matapishi, kinyesi, mkojo au kikohozi"),
        "do": [
            T("Let the person lie down and rest. If they are vomiting, lay them on their side.",
              "Mlaze apumzike. Ikiwa anatapika, mlaze ubavuni."),
            T("Get to a health facility today, or now if there is a lot of blood or they feel faint.",
              "Nenda kituo cha afya leo, au sasa ikiwa kuna damu nyingi au anahisi kuzimia."),
            T("Tell the health worker how much blood and for how long.",
              "Mweleze mhudumu wa afya kiasi cha damu na kwa muda gani."),
        ],
        "dont": [
            T("Do not give food or drink if they are vomiting blood.",
              "Usimpe chakula wala kinywaji ikiwa anatapika damu."),
        ],
    },
    {
        "id": "abdomen", "priority": 12,
        "codes": {"abdominal_rigidity", "acute_liver_failure"},
        "title": T("Severe belly pain or a hard belly", "Maumivu makali ya tumbo au tumbo gumu"),
        "do": [
            T("Let the person lie in the most comfortable position.",
              "Mlaze katika nafasi anayojisikia vizuri."),
            T("Get to a health facility now.", "Nenda kituo cha afya sasa."),
        ],
        "dont": [
            T("Do not give food or drink. They may need an operation.",
              "Usimpe chakula wala kinywaji. Huenda akahitaji upasuaji."),
        ],
    },
    {
        "id": "meningitis", "priority": 13,
        "codes": {"stiff_neck", "photophobia", "bulging_fontanelle", "purpuric_rash"},
        "requires_any": {"high_fever", "mild_fever", "bulging_fontanelle", "purpuric_rash"},
        "title": T("Stiff neck with fever: possible meningitis", "Shingo ngumu na homa: huenda ni homa ya uti wa mgongo"),
        "do": [
            T("Get to a health facility now. This can get worse within hours.",
              "Nenda kituo cha afya sasa. Hali hii inaweza kuzidi ndani ya saa chache."),
            T("Keep the person calm and comfortable while you arrange transport.",
              "Mtulize mtu na umweke vizuri wakati unapanga usafiri."),
        ],
        "dont": [
            T("Do not wait for the fever to go down.", "Usisubiri homa ipungue."),
        ],
    },
    {
        "id": "child_danger", "priority": 14,
        "codes": {"unable_to_drink", "vomits_everything", "unable_to_breastfeed", "unable_to_sit", "failure_to_thrive",
                  "kwashiorkor_signs", "severe_pallor"},
        "title": T("Child danger signs", "Dalili za hatari kwa mtoto"),
        "do": [
            T("A child who cannot drink or breastfeed, vomits everything, is very sleepy, or has had a fit must be seen at a health facility now.",
              "Mtoto asiyeweza kunywa au kunyonya, anayetapika kila kitu, aliye na usingizi mwingi, au aliyepata degedege lazima aonwe kituo cha afya sasa."),
            T("Keep the child warm. Keep breastfeeding if the child can suck.",
              "Mfunike mtoto apate joto. Endelea kunyonyesha ikiwa anaweza kunyonya."),
            T("Offer small sips of drink on the way if the child can swallow.",
              "Mpe mtoto funda ndogo za kinywaji njiani ikiwa anaweza kumeza."),
        ],
        "dont": [
            T("Do not wait. Children can get worse very quickly.",
              "Usisubiri. Watoto wanaweza kuzidiwa haraka sana."),
        ],
    },
    {
        "id": "dehydration", "priority": 15,
        "codes": {"dehydration", "sunken_eyes", "diarrhoea", "vomiting", "unable_to_drink"},
        "title": T("Diarrhoea or vomiting: prevent dehydration", "Kuhara au kutapika: zuia upungufu wa maji mwilini"),
        "do": [
            T("Give oral rehydration solution (ORS) in small, frequent sips. For a young child, a teaspoon every 1 to 2 minutes.",
              "Mpe mmumunyo wa chumvi na sukari (ORS) kwa funda ndogo mara kwa mara. Kwa mtoto mdogo, kijiko kidogo kila dakika 1 hadi 2."),
            T("If they vomit, wait 10 minutes, then continue more slowly.",
              "Wakitapika, subiri dakika 10, kisha endelea polepole zaidi."),
            T("Keep feeding and breastfeeding as usual.",
              "Endelea kulisha na kunyonyesha kama kawaida."),
            T("Go to a health facility if there is blood in the stool, repeated vomiting, sunken eyes, very sleepy, very thirsty, not passing urine, fever, or it lasts more than 2 days.",
              "Nenda kituo cha afya ikiwa kuna damu kwenye kinyesi, kutapika mara kwa mara, macho kuzama, usingizi mwingi, kiu kali, kutokojoa, homa, au inazidi siku 2."),
        ],
        "dont": [
            T("Do not stop giving fluids.", "Usiache kutoa vinywaji."),
        ],
    },
    {
        "id": "fever", "priority": 16,
        "codes": {"high_fever", "mild_fever", "malaria_confirmed"},
        "title": T("Fever: get tested", "Homa: pima"),
        "do": [
            T("Get a malaria test at a health facility today. Untreated malaria can become severe within 24 hours.",
              "Pima malaria kituo cha afya leo. Malaria isiyotibiwa inaweza kuwa kali ndani ya saa 24."),
            T("Rest and drink plenty of safe fluids.",
              "Pumzika na unywe maji safi mengi."),
            T("Go now if there are fits, trouble breathing, extreme weakness, confusion, dark or bloody urine, yellow eyes, or bleeding.",
              "Nenda sasa ikiwa kuna degedege, kupumua kwa shida, udhaifu mkubwa, kuchanganyikiwa, mkojo mweusi au wenye damu, macho ya njano, au kutokwa damu."),
        ],
        "dont": [
            T("Do not wait several days to see if the fever goes away.",
              "Usisubiri siku kadhaa kuona kama homa itaisha."),
        ],
    },
]

AGE_NOTES = {
    "infant": T("This is a baby under 1 year. Babies can get worse very quickly. SACA has not been tested on babies, so see a health worker even if the result is low.",
                "Huyu ni mtoto mchanga chini ya mwaka 1. Watoto wachanga wanaweza kuzidiwa haraka sana. SACA haijajaribiwa kwa watoto wachanga, kwa hiyo muone mhudumu wa afya hata kama matokeo ni ya chini."),
    "young_child": T("This is a child under 5. Young children can get worse quickly. SACA has not been tested on children, so be extra careful.",
                     "Huyu ni mtoto chini ya miaka 5. Watoto wadogo wanaweza kuzidiwa haraka. SACA haijajaribiwa kwa watoto, kwa hiyo kuwa makini zaidi."),
    "child": T("This is a child. SACA has not been tested on children, so be extra careful.",
               "Huyu ni mtoto. SACA haijajaribiwa kwa watoto, kwa hiyo kuwa makini zaidi."),
    "older_adult": T("Older adults can get worse faster. If you are unsure, see a health worker.",
                     "Wazee wanaweza kuzidiwa haraka zaidi. Ikiwa huna uhakika, muone mhudumu wa afya."),
}

DURATION_NOTES = {
    "long": T("The symptoms have lasted a week or more. Even if the result is low, a health worker should check this.",
              "Dalili zimedumu wiki moja au zaidi. Hata kama matokeo ni ya chini, mhudumu wa afya anapaswa kuchunguza."),
}

CAVEAT = T("This is general advice, not a diagnosis. It has not yet been reviewed by a clinician.",
           "Huu ni ushauri wa jumla, si uchunguzi wa daktari. Bado haujakaguliwa na mtaalamu wa afya.")



MAX_TOPICS = 3

# --------------------------------------------------------------------------
# Medicine information (client request: "medicine recommendations").
# Over-the-counter information only, from WHO and NHS public pages. NO DOSES: always "follow the packet or ask a
# pharmacist". Shown only for LOW and MEDIUM results. For HIGH and CRITICAL the only message is "do not delay care".
# Must be signed off by a clinician before real use.
# --------------------------------------------------------------------------
PAIN_FEVER_CODES = {"high_fever", "mild_fever", "headache", "muscle_pain", "joint_pain", "back_pain", "neck_pain",
                    "knee_pain", "hip_joint_pain", "throat_irritation", "patches_in_throat", "pain_behind_the_eyes",
                    "chills", "malaise"}
FEVER_CODES = {"high_fever", "mild_fever", "chills", "shivering"}
COLD_CODES = {"cough", "runny_nose", "congestion", "continuous_sneezing", "throat_irritation", "sinus_pressure",
              "phlegm", "mucoid_sputum"}
GUT_CODES = {"diarrhoea", "vomiting", "dehydration"}

MED_URGENT = [
    T("Do not delay getting care to buy or take medicine.",
      "Usichelewe kupata huduma ili kununua au kutumia dawa."),
    T("Do not give anything by mouth if the person is very sleepy, fitting or unconscious.",
      "Usimpe chochote kwa mdomo ikiwa ana usingizi mwingi, ana degedege au amepoteza fahamu."),
    T("Take any medicines the person already uses, or their packets, with you to show the health worker.",
      "Chukua dawa anazotumia tayari, au paketi zake, umwonyeshe mhudumu wa afya."),
]

MED_NOT_ASSESSED = [
    T("SACA cannot give medicine information when it could not read the symptoms. Ask a health worker or pharmacist.",
      "SACA haiwezi kutoa taarifa za dawa ilipokosa kuelewa dalili. Muulize mhudumu wa afya au mfamasia."),
]

MED_GENERAL = [
    T("Always follow the dose on the packet for the person's age, or ask a pharmacist. SACA does not give doses.",
      "Daima fuata kipimo kilichoandikwa kwenye paketi kulingana na umri, au muulize mfamasia. SACA haitoi vipimo vya dawa."),
    T("If someone has taken more than the packet says, get medical help straight away.",
      "Ikiwa mtu ametumia zaidi ya kilichoandikwa kwenye paketi, tafuta msaada wa matibabu mara moja."),
]

MEDICINES = [
    {
        "id": "paracetamol", "codes": PAIN_FEVER_CODES, "min_age_months": 2,
        "title": T("Paracetamol (for pain or fever)", "Paracetamol (kwa maumivu au homa)"),
        "points": [
            T("Paracetamol can ease pain and bring down a fever.",
              "Paracetamol inaweza kupunguza maumivu na kushusha homa."),
            T("Do not take it with other medicines that also contain paracetamol, such as cold and flu remedies.",
              "Usiitumie pamoja na dawa nyingine zenye paracetamol, kama dawa za mafua."),
            T("Do not take it for more than 3 days unless a health worker says so.",
              "Usiitumie zaidi ya siku 3 isipokuwa mhudumu wa afya akisema."),
        ],
        "cautions": [
            T("Ask a health worker first if the person has liver or kidney problems or drinks a lot of alcohol.",
              "Muulize mhudumu wa afya kwanza ikiwa mtu ana tatizo la ini au figo au anakunywa pombe nyingi."),
        ],
        "pregnancy": T("In pregnancy, paracetamol is usually the best painkiller to use.",
                       "Wakati wa ujauzito, paracetamol kwa kawaida ndiyo dawa bora ya maumivu."),
        "too_young": T("Not for babies under 2 months. Take the baby to a health worker.",
                       "Si kwa watoto chini ya miezi 2. Mpeleke mtoto kwa mhudumu wa afya."),
    },
    {
        "id": "ibuprofen", "codes": PAIN_FEVER_CODES, "min_age_months": 3, "not_in_pregnancy": True,
        "not_with": {"dehydration", "diarrhoea", "vomiting", "stomach_bleeding", "bloody_stool", "breathlessness"},
        "title": T("Ibuprofen (another option for pain or fever)", "Ibuprofen (chaguo jingine kwa maumivu au homa)"),
        "points": [
            T("Ibuprofen can also ease pain and fever, but it is not safe for everyone.",
              "Ibuprofen pia inaweza kupunguza maumivu na homa, lakini si salama kwa kila mtu."),
        ],
        "cautions": [
            T("Do not use it if the person has a stomach ulcer, kidney, liver or heart problems, has had a stroke, or has chickenpox.",
              "Usiitumie ikiwa mtu ana kidonda cha tumbo, tatizo la figo, ini au moyo, amewahi kupata kiharusi, au ana tetekuwanga."),
            T("People with asthma should ask a pharmacist first.",
              "Watu wenye pumu wamuulize mfamasia kwanza."),
            T("Do not give it to a child who is dehydrated.",
              "Usimpe mtoto aliyepungukiwa na maji mwilini."),
        ],
        "pregnancy_block": T("Do not use ibuprofen in pregnancy unless a doctor or pharmacist says so.",
                             "Usitumie ibuprofen wakati wa ujauzito isipokuwa daktari au mfamasia akisema."),
    },
    {
        "id": "aspirin", "codes": PAIN_FEVER_CODES, "warning_only": True,
        "title": T("Aspirin: not for children", "Aspirin: si kwa watoto"),
        "points": [
            T("Never give aspirin to anyone under 16 unless a doctor prescribed it. It can cause a rare but dangerous illness (Reye's syndrome).",
              "Kamwe usimpe aspirin mtu chini ya miaka 16 isipokuwa daktari ameiandika. Inaweza kusababisha ugonjwa nadra lakini hatari (Reye's syndrome)."),
        ],
    },
    {
        "id": "malaria_test", "codes": FEVER_CODES, "warning_only": True,
        "title": T("Malaria medicine: test first", "Dawa ya malaria: pima kwanza"),
        "points": [
            T("Do not take malaria medicine without a test. WHO advises a malaria test (rapid test or microscope) before treatment.",
              "Usitumie dawa ya malaria bila kupima. WHO inashauri kupima malaria (kipimo cha haraka au hadubini) kabla ya matibabu."),
            T("Get tested within 24 hours of the fever starting. If the test is positive, the health worker will give the right medicine.",
              "Pima ndani ya saa 24 tangu homa ianze. Kipimo kikionyesha malaria, mhudumu wa afya atakupa dawa sahihi."),
        ],
    },
    {
        "id": "ors_zinc", "codes": GUT_CODES,
        "title": T("ORS (and zinc for children) for diarrhoea", "ORS (na zinki kwa watoto) kwa kuhara"),
        "points": [
            T("Oral rehydration solution (ORS) replaces the water and salts lost through diarrhoea. Get ORS sachets from a pharmacy or health facility.",
              "Mmumunyo wa ORS hurudisha maji na chumvi zilizopotea kwa kuhara. Pata pakiti za ORS kutoka duka la dawa au kituo cha afya."),
            T("Mix ORS with clean water exactly as the packet says.",
              "Changanya ORS na maji safi kama ilivyoandikwa kwenye paketi."),
            T("For a child with diarrhoea, WHO advises zinc tablets for 10 to 14 days. Ask a health worker or pharmacist for them.",
              "Kwa mtoto mwenye kuhara, WHO inashauri vidonge vya zinki kwa siku 10 hadi 14. Muulize mhudumu wa afya au mfamasia."),
        ],
        "cautions": [
            T("Go to a health facility if there is blood in the stool or the person cannot drink.",
              "Nenda kituo cha afya ikiwa kuna damu kwenye kinyesi au mtu hawezi kunywa."),
        ],
    },
    {
        "id": "cold", "codes": COLD_CODES, "warning_only": True,
        "title": T("Cough and cold medicines", "Dawa za kikohozi na mafua"),
        "points": [
            T("Colds are caused by viruses. Antibiotics do not help a cold. Only take antibiotics if a health worker prescribes them.",
              "Mafua husababishwa na virusi. Antibiotiki hazisaidii mafua. Tumia antibiotiki tu ikiwa mhudumu wa afya ameziandika."),
            T("Ask a pharmacist before giving any cough or cold medicine to a child. Some are not for children under 12, and decongestants are not for children under 6.",
              "Muulize mfamasia kabla ya kumpa mtoto dawa yoyote ya kikohozi au mafua. Baadhi si kwa watoto chini ya miaka 12, na dawa za kufungua pua si kwa watoto chini ya miaka 6."),
        ],
    },
]

MEDICINE_SOURCES = [
    "NHS: Paracetamol for adults (nhs.uk/medicines/paracetamol-for-adults): uses, cautions, not with other paracetamol products, 3-day limit, best painkiller in pregnancy.",
    "NHS: Who can and cannot take ibuprofen (nhs.uk/medicines/ibuprofen-for-adults): ulcer, asthma, chickenpox, heart/liver/kidney, stroke, avoid in pregnancy.",
    "NHS: Medicines for babies and children (nhs.uk/baby/health/medicines-for-babies-and-children): no aspirin under 16, paracetamol from 2 months, ibuprofen from 3 months and over 5 kg, no ibuprofen if dehydrated or chickenpox.",
    "NHS: Cough and Common cold pages: honey not under 1, some cough medicines not under 12, decongestants not under 6, antibiotics do not help colds, see a GP if a cough lasts over 3 weeks.",
    "WHO fact sheet: Diarrhoeal disease: ORS, 10-14 day zinc course, keep feeding, severe dehydration signs.",
    "WHO Global Malaria Programme, treatment: parasitological confirmation (microscopy or RDT) before treatment; prompt treatment within 24 hours of fever onset.",
]


def _age_months(age_years, age_months_total=None):
    if age_months_total is not None:
        return age_months_total
    if age_years is None:
        return None
    return age_years * 12


BABY_ASK = T("For a baby under 1 year, ask a health worker before giving any medicine.",
             "Kwa mtoto mchanga chini ya mwaka 1, muulize mhudumu wa afya kabla ya kumpa dawa yoyote.")


def build_medicine(key, codes, age_months=None, pregnant=False, age_estimated=False):
    """
    Medicine information for one result. key is the tier key (LOW/MEDIUM/HIGH/CRITICAL/NOT_ASSESSED).
    age_estimated: the age was typed in whole years, so a "0" can mean any age from birth to 11 months; the
    2-month and 3-month limits cannot be checked, and every medicine with a minimum age is withheld.
    """
    if key in ("HIGH", "CRITICAL"):
        return {"mode": "urgent", "items": [], "general": MED_URGENT}
    if key == "NOT_ASSESSED":
        return {"mode": "none", "items": [], "general": MED_NOT_ASSESSED}

    items = []
    for med in MEDICINES:
        if not (med["codes"] & codes):
            continue
        if med["id"] == "aspirin" and age_months is not None and age_months >= 16 * 12:
            continue  # the warning is about children; an adult does not need it
        entry = {"id": med["id"], "title": med["title"], "points": list(med["points"]),
                 "cautions": list(med.get("cautions", [])), "blocked": False}
        min_age = med.get("min_age_months")
        if min_age is not None and age_estimated and age_months is not None and age_months < 12:
            entry["blocked"] = True
            entry["points"] = [BABY_ASK]
            entry["cautions"] = []
        elif min_age is not None and age_months is not None and age_months < min_age:
            entry["blocked"] = True
            entry["points"] = [med.get("too_young") or T(
                "Not suitable at this age. Ask a health worker.", "Haifai kwa umri huu. Muulize mhudumu wa afya.")]
            entry["cautions"] = []
        elif pregnant and med.get("not_in_pregnancy"):
            entry["blocked"] = True
            entry["points"] = [med["pregnancy_block"]]
            entry["cautions"] = []
        elif med.get("not_with") and (med["not_with"] & codes):
            entry["blocked"] = True
            entry["points"] = [T("Not advised with these symptoms. Use paracetamol instead or ask a pharmacist.",
                                 "Haishauriwi kwa dalili hizi. Tumia paracetamol badala yake au muulize mfamasia.")]
            entry["cautions"] = []
        elif pregnant and med.get("pregnancy"):
            entry["points"].append(med["pregnancy"])
        items.append(entry)

    return {"mode": "info" if items else "none_matched", "items": items,
            "general": MED_GENERAL if items else [
                T("SACA has no medicine information for these symptoms. Ask a pharmacist or health worker.",
                  "SACA haina taarifa za dawa kwa dalili hizi. Muulize mfamasia au mhudumu wa afya.")]}


def _topic_matches(topic, codes):
    hits = topic["codes"] & codes
    if not hits:
        return False
    required = topic.get("requires_any")
    if required and not (required & codes):
        return False
    return True


def topics_for(codes):
    """Return the matching first-aid topics, most urgent first (at most MAX_TOPICS)."""
    codes = set(codes or [])
    matched = [t for t in TOPICS if _topic_matches(t, codes)]
    matched.sort(key=lambda t: t["priority"])
    return matched[:MAX_TOPICS]


def symptom_self_care(codes):
    out = []
    for group in SYMPTOM_SELF_CARE:
        if group["codes"] & codes:
            out.extend(group["items"])
    return out


def build_guidance(severity, assessed=True, codes=None, age_group=None, pregnant=None, duration=None,
                   age_years=None, age_months_total=None, age_estimated=False):
    """
    Build the four result cards' content for one assessment.

    severity  LOW / MEDIUM / HIGH / CRITICAL
    assessed  False when SACA could not read the symptoms
    codes     the symptom codes SACA recognised
    Returns a dict with "clinic" (doctor / clinic advice), "self_care", "medicine", plus the headline and caveats.
    """
    key = severity if (assessed and severity in TIERS) else "NOT_ASSESSED"
    tier = TIERS[key]
    codes = set(codes or [])
    topic_codes = set(codes)
    # A pregnant woman with a serious result and headache or vision trouble: show the pregnancy danger-sign topic.
    if pregnant and key in ("HIGH", "CRITICAL") and \
            topic_codes & {"headache", "visual_disturbances", "blurred_and_distorted_vision", "high_fever",
                           "abdominal_pain", "belly_pain", "stomach_pain"}:
        topic_codes.add("pre_eclampsia")
    topics = topics_for(topic_codes)

    notes = []
    if age_group in AGE_NOTES:
        notes.append(AGE_NOTES[age_group])
    if pregnant:
        notes.append(T("The person is pregnant. Tell the health worker, and go sooner rather than later.",
                       "Mtu huyu ni mjamzito. Mwambie mhudumu wa afya, na uende mapema."))
    if duration == "long" and key in ("LOW", "MEDIUM"):
        notes.append(DURATION_NOTES["long"])

    self_care_steps = list(SELF_CARE[key])
    if key in ("LOW", "MEDIUM"):
        self_care_steps.extend(symptom_self_care(codes))

    medicine = build_medicine(key, codes, _age_months(age_years, age_months_total), bool(pregnant),
                              bool(age_estimated))
    topic_list = [{"id": t["id"], "title": t["title"], "do": t["do"], "dont": t["dont"]} for t in topics]
    danger = DANGER_SIGNS if key in ("LOW", "MEDIUM") else None

    return {
        "level_key": key,
        "level": LEVEL_NAMES[key],
        "headline": tier["headline"],
        "timeframe": tier["timeframe"],
        "clinic": {"headline": tier["headline"], "timeframe": tier["timeframe"], "steps": tier["steps"],
                   "notes": notes},
        "self_care": {"steps": self_care_steps, "topics": topic_list, "danger_signs": danger},
        "medicine": medicine,
        # flat keys kept for older callers
        "steps": tier["steps"],
        "topics": topic_list,
        "danger_signs": danger,
        "notes": notes,
        "caveat": CAVEAT,
        "status": GUIDANCE_STATUS,
        "version": GUIDANCE_VERSION,
    }


def spoken_summary(guidance, lang="en"):
    """A short text for read-aloud: headline, timeframe and the first specific first-aid steps."""
    lang = lang if lang in ("en", "sw") else "en"
    parts = [guidance["headline"][lang], guidance["timeframe"][lang]]
    for topic in guidance["topics"][:1]:
        parts.append(topic["title"][lang] + ".")
        parts.extend(step[lang] for step in topic["do"][:3])
    return " ".join(parts)
