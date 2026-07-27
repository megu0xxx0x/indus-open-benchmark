# Annotation Guide

## Preserve the observation

Annotate what is visible before deciding what it means. A fish-like shape is a shape, not the word
“fish.” A repeated final sign is positionally final, not automatically a suffix.

## Image and orientation

1. Identify whether the image shows a matrix, impression, direct inscription, drawing, or an
   uncertain transformation.
2. Store tokens in left-to-right image order as `visual_index`, starting at zero.
3. Store inferred linguistic order separately as `reading_index`.
4. If direction is unknown, leave `reading_index` null. Do not encode a preferred theory as fact.
5. Never mirror pixels without preserving the original image and transformation metadata.

## Segmentation

- One token is one intentionally produced sign instance, not one connected component.
- Preserve ligatures and composite-sign uncertainty as alternatives rather than cutting to fit a
  preferred sign list.
- Draw geometry around the incision or impression, excluding adjacent motif lines where possible.
- Record gaps, edge loss, abrasion, modern damage, and restoration separately in notes.

## Identification

- Use stable project sign IDs; keep Mahadevan, Parpola, Wells, and other catalogues in crosswalks.
- Do not collapse allographs at ingestion. Record proposed groupings in a versioned analysis layer.
- Null `sign_id` is preferable to a forced classification.
- Confidence is the probability assigned to the selected transcription under the available image,
  not a measure of how plausible a decipherment would be.

Suggested interpretation:

| Confidence | Meaning |
|---:|---|
| `1.0` | Synthetic fixture or independently verified exact observation |
| `0.90–0.99` | Clear form with negligible catalogue ambiguity |
| `0.60–0.89` | Preferred identification but a credible alternative exists |
| `0.01–0.59` | Weak identification; alternatives must be recorded |
| `0.0` | Unreadable or deliberately unclassified |

## Independent annotation

Each priority artifact should be transcribed independently by at least two annotators. Adjudicators
see both records only after the independent pass. Preserve:

- both original annotations;
- adjudicated observation;
- reason for the decision;
- image version and viewing method;
- annotator role and date;
- whether RTI, 3D, microscopy, or only a catalogue drawing was available.

Agreement must be reported separately for segmentation, sign identity, condition, and direction.

## Duplicate handling

Link, rather than delete:

- multiple publications of one object;
- different photographs of one object;
- seal and impression;
- casts and replicas;
- exact or near-exact texts;
- suspected shared molds or workshop templates.

The most conservative family identifier governs benchmark splitting until the relationship is
resolved.
