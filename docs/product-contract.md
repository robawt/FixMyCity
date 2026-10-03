# FixMyCity Product Contract

## Input
- text: optional/required depending on flow
- photo: optional
- GPS coordinates
- GPS accuracy
- timestamp
- QR site ID: optional

## Issue Types
- pothole
- road_damage
- streetlight
- water_leak
- drainage
- flooding
- sanitation
- fallen_tree
- electrical_hazard
- obstruction
- other

## Service Owners
- GHMC
- Cyberabad Municipal Corporation
- Malkajgiri Municipal Corporation
- Water/Sewerage
- Electricity
- HYDRAA
- Other/Review

## Severity Dimensions
- safety
- immediacy
- public impact
- context
- current conditions

## Important Context
- traffic
- road type
- nearby school/hospital/transit
- rainfall
- hotspot
- recurrence
- incident age

## Rules
Emotional language contributes zero severity.

Never invent:
- locations
- dates
- measurements
- causes
- people affected

High-risk + uncertain:
urgent verification.

Duplicate reports:
cluster into one incident when issue/location/time indicate the same event.

Synthetic demo data must be clearly separated from real data.