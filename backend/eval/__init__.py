"""Offline simulated-learner evaluation.

Not part of the shipped app: nothing here is imported by backend/graph.py,
backend/api.py, or any node. It exists to answer one question the deployed
engine can't answer about itself -- across many synthetic students with a
hidden true mastery per skill, how many actually learn all four skills under
the real adaptive engine versus a fixed-difficulty, non-adaptive baseline.
See docs/ for the feasibility write-up this package implements.
"""
