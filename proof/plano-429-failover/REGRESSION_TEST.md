# Plano 429 Cooldown Regression Test

This note captures the one invariant that makes 429-safe retry/failover real in practice.

**Cooldown must be consulted by provider selection, not only by the retry loop.**

If a model or provider is in `cooldown_until > now`, it must be **ineligible for reselection** across attempts. Otherwise a gateway can “honor Retry-After” and still thrash via routing.

---

## Invariant

When a response yields `429` with a valid `Retry-After` header:

- Record cooldown state:

```
cooldown_until = now + retry_after_seconds
```

- Provider/model selection must exclude that entry until the cooldown expires.

Conceptual selection rule:

```
eligible_providers = providers.filter(p => p.cooldown_until <= now)
selected_provider = select(eligible_providers)
```

---

## Minimal Regression Test (Behavioral)

Given two providers/models:

- **A** — preferred/default  
- **B** — fallback

### Step 1
First attempt selects **A** and returns:

- HTTP status: `429`
- Header: `Retry-After: 2`

### Step 2
Next selection attempt occurs at **t = 0.5 seconds**

**Assert:**

- **A is not eligible** until `t >= 2.0s`
- **B remains eligible** and may be selected

### Step 3
Next selection attempt occurs at **t = 2.0 seconds**

**Assert:**

- **A becomes eligible again**

---

## Open Questions (Documented Assumptions)

### Cooldown Key / Scope

A reasonable first implementation key is:

```
model | provider
```

In real production systems, rate limits are often scoped by:

```
{ provider, api_key, region }
```

(and sometimes organization or project).

If Plano cannot support deeper scoping yet, the implementation should **document the assumed scope** and choose the safest default.

---

### 429 Without Retry-After

Two defensible approaches:

**1. STOP**

Do not retry without an explicit cooldown signal.

Safest against retry storms.

**2. Backoff with Bounds**

Fallback to exponential backoff with jitter, but enforce:

- maximum attempts
- maximum retry duration

Whichever behavior is chosen should be **explicit and bounded** so the system cannot spin indefinitely.