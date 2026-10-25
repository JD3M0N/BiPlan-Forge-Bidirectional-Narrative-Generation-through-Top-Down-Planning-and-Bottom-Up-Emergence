"""The typography a model's prose and its own quotes are compared through."""

# Curly quotes, guillemets and the two dashes a model mixes freely within one run, folded to
# their ASCII twin. Comparing a critic's quote against the draft it came from fails on the
# style alone otherwise, which is how an approval with a real quote came back unjudged.
TYPOGRAPHY = str.maketrans(
    {"“": '"', "”": '"', "«": '"', "»": '"', "‘": "'", "’": "'", "—": "-", "–": "-"}
)
