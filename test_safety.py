# test_safety.py

from ammu_safety import check_reply

# a good CRITICAL reply (has serious wording, facility, not a doctor line)
good = "This looks serious. Please go to a medical facility right away. Remember, I am not a doctor."
print("good reply passes?", check_reply(good, "CRITICAL", "convulsions"))

# a bad reply that dropped the facility and the not a doctor line
bad = "This looks serious. You will probably be fine, do not worry."
print("bad reply passes?", check_reply(bad, "CRITICAL", "convulsions"))

# a bad reply that forgot the not a doctor line
bad2 = "This looks serious. Please go to a medical facility right away."
print("bad2 reply passes?", check_reply(bad2, "CRITICAL", "convulsions"))