"""Hand-checked Stoic quotes (common English translations). AI never writes or edits these;
popular misattributions ("Throw me to the wolves...", "Everything we hear is an opinion...") are excluded.

(quote, author, source)
"""
QUOTES = [
    # Marcus Aurelius, Meditations
    ("Waste no more time arguing about what a good man should be. Be one.", "Marcus Aurelius", "Meditations"),
    ("The best revenge is not to be like your enemy.", "Marcus Aurelius", "Meditations"),
    ("Very little is needed to make a happy life; it is all within yourself, in your way of thinking.", "Marcus Aurelius", "Meditations"),
    ("If it is not right, do not do it; if it is not true, do not say it.", "Marcus Aurelius", "Meditations"),
    ("The soul becomes dyed with the colour of its thoughts.", "Marcus Aurelius", "Meditations"),
    ("Loss is nothing else but change, and change is Nature's delight.", "Marcus Aurelius", "Meditations"),
    ("Do every act of your life as though it were the very last act of your life.", "Marcus Aurelius", "Meditations"),
    ("How much more grievous are the consequences of anger than the causes of it.", "Marcus Aurelius", "Meditations"),
    ("Never esteem anything as of advantage to you that will make you break your word or lose your self-respect.", "Marcus Aurelius", "Meditations"),
    ("Dwell on the beauty of life. Watch the stars, and see yourself running with them.", "Marcus Aurelius", "Meditations"),
    ("Never let the future disturb you. You will meet it, if you have to, with the same weapons of reason which today arm you against the present.", "Marcus Aurelius", "Meditations"),
    ("Accept the things to which fate binds you, and love the people with whom fate brings you together.", "Marcus Aurelius", "Meditations"),
    ("The object of life is not to be on the side of the majority, but to escape finding oneself in the ranks of the insane.", "Marcus Aurelius", "Meditations"),
    ("The happiness of your life depends upon the quality of your thoughts.", "Marcus Aurelius", "Meditations"),
    ("When another blames you or hates you, approach their souls, penetrate within, and see what kind of people they are.", "Marcus Aurelius", "Meditations"),
    ("Look within. Within is the fountain of good, and it will ever bubble up, if you will ever dig.", "Marcus Aurelius", "Meditations"),
    # Seneca, Letters / essays
    ("We suffer more often in imagination than in reality.", "Seneca", "Letters to Lucilius"),
    ("It is not that we have a short time to live, but that we waste a lot of it.", "Seneca", "On the Shortness of Life"),
    ("Difficulties strengthen the mind, as labour does the body.", "Seneca", "Letters to Lucilius"),
    ("While we are postponing, life speeds by.", "Seneca", "Letters to Lucilius"),
    ("No man was ever wise by chance.", "Seneca", "Letters to Lucilius"),
    ("Begin at once to live, and count each separate day as a separate life.", "Seneca", "Letters to Lucilius"),
    ("Associate with people who are likely to improve you.", "Seneca", "Letters to Lucilius"),
    ("If a man knows not to which port he sails, no wind is favourable.", "Seneca", "Letters to Lucilius"),
    ("Wherever there is a human being, there is an opportunity for a kindness.", "Seneca", "On the Happy Life"),
    ("It is a rough road that leads to the heights of greatness.", "Seneca", "Letters to Lucilius"),
    ("Until we have begun to go without them, we fail to realise how unnecessary many things are.", "Seneca", "Letters to Lucilius"),
    ("Most powerful is he who has himself in his own power.", "Seneca", "Letters to Lucilius"),
    ("As is a tale, so is life: not how long it is, but how good it is, is what matters.", "Seneca", "Letters to Lucilius"),
    ("Sometimes even to live is an act of courage.", "Seneca", "Letters to Lucilius"),
    ("He who is brave is free.", "Seneca", "Letters to Lucilius"),
    # Epictetus, Enchiridion / Discourses
    ("Men are disturbed not by things, but by the opinions about things.", "Epictetus", "Enchiridion"),
    ("First say to yourself what you would be; and then do what you have to do.", "Epictetus", "Discourses"),
    ("No man is free who is not master of himself.", "Epictetus", "Fragments"),
    ("If you want to improve, be content to be thought foolish and stupid.", "Epictetus", "Enchiridion"),
    ("Make the best use of what is in your power, and take the rest as it happens.", "Epictetus", "Discourses"),
    ("He is a wise man who does not grieve for the things which he has not, but rejoices for those which he has.", "Epictetus", "Fragments"),
    ("Only the educated are free.", "Epictetus", "Discourses"),
    ("Some things are within our power, while others are not.", "Epictetus", "Enchiridion"),
    ("Circumstances don't make the man, they only reveal him to himself.", "Epictetus", "Discourses"),
    ("It is impossible for a man to learn what he thinks he already knows.", "Epictetus", "Discourses"),
]

# Moody backgrounds for the Stoic account (search query, tags one of which must appear)
BACKDROPS = [
    ("storm clouds", ["storm", "cloud"]), ("foggy forest", ["fog", "mist"]), ("ocean waves dark", ["wave", "ocean", "sea"]),
    ("mountain fog", ["mountain", "fog"]), ("night sky stars", ["star", "night", "milky way"]),
    ("rain window", ["rain"]), ("candle flame", ["candle", "flame"]), ("lightning", ["lightning", "thunder"]),
    ("desert dunes", ["desert", "dune", "sand"]), ("snow mountains", ["snow", "mountain"]),
    ("waterfall", ["waterfall"]), ("sunrise mountains", ["sunrise", "mountain"]), ("campfire night", ["fire", "campfire"]),
    ("lone tree", ["tree"]), ("dark sea", ["sea", "ocean"]), ("clouds timelapse", ["cloud", "sky"]),
]
