# Governance and the human gate (all agents)

## Why a gate
An autonomous system that can make irreversible changes without review is not
deployable on a real site, regardless of how good its reasoning is. The gate is
the product, not a limitation of it.

## Risk scoring
Risk is computed deterministically from the action, its blast radius, the water
it moves and the animals it affects. A model may raise a severity or a risk
flag. A model may never lower one, and no model sets the score.

## Autonomy tiers
Actions that change nothing physical run without approval. Actions that recover
within minutes run below a low ceiling. Actions that commit water, welfare or
money always require a person.

## Audit
Every decision is recorded with the agent, the action, the risk, the verdict and
the reason it was gated. An action taken without a human is recorded too, marked
as automatic.
