# Alcohol Label Verification App

## Introduction

This is my submission for the Treasury take-home test.

The application is a prototype for checking alcohol label artwork against
structured application data. It is not meant to be a final legal approval system.
The goal is to show the product approach: what inputs I chose, what I decided not
to support, and how I balanced speed, accuracy, and usability.

At a technical level, I chose a fairly standard web stack on purpose: React and
TypeScript for the frontend, FastAPI for the backend, Docker for a repeatable
runtime, and OpenRouter for hosted model access. 

## Demo Testing Controls

The app includes two demo-marked buttons that are only there to provide sample labels
for testing.

One button creates a large spreadsheet-style batch with roughly 300 labels. I
included this because large-batch handling was one of the requirements I wanted
to make easy to test.

The other button loads sample labels and applications that are expected to either
pass or fail. These samples include deliberate edits and mismatches, such as
labels where the government warning was removed or blurred, and application form
values where the alcohol percentage does not match the label. I also included a
few passing samples that were deliberately edited with glare or rotated labels,
because those should still pass when the required information is visible. 

## Design Decisions

### Label Extraction

For label extraction, I chose not to make one large model call responsible for
everything. The app splits each review into three focused vision-model calls:
one for legibility and the government warning, one for product fields like
brand, class/type, alcohol content, net contents, and color disclosures, and one
for origin-related fields like name/address and country of origin. I did this
because labels are visually dense, and smaller prompts make it easier to keep the
model focused on the evidence it is supposed to read instead of asking it to
solve the whole review in one pass. The tradeoff here is extra expense when 
you do three times the amount of LLM calls, though these models are fairly lightweight, and very cost efficient, 
even at scale. We are also able to not sacrifice much in terms of processing time increases, 
due to the ability to run all three LLM calls in parallel. 

I also kept the model contract JSON-first: the prompt asks for structured JSON,  and the 
backend parses the response into typed field results. That makes the result easier to 
audit in the UI and gives the backend something deterministic to validate instead of a 
loose paragraph of model output. Finally, the app runs a verification guard after the
model responds. The guard exists because the model can still be overconfident,
especially on things like alcohol-content normalization, beverage-class
conflicts, missing label values, or the exact government warning text. If the
model says a field passed but the structured evidence does not support that
pass, the guard can turn it into a fail before the result reaches the reviewer.


### Input Format

The first major design decision was the input format. When I started, I looked at
COLA examples where the label and application often appeared together in one
combined image. My first idea was to let users upload that combined image and
have the model pull out both the application text and the label text, then
compare the two.

That approach had some appeal. It felt native to the way the COLA source data was
already presented, and it would make batch upload very easy: users could upload a
large set of images without matching each label to a separate text record or
second image.

I moved away from that approach for two reasons. First, it did not seem aligned
with what the take-home assessment was asking for. Second, those scraped combined
images came from a place where the application and label were already matched.
That is not necessarily the real user workflow. If a user did not already have
the two documents joined together, asking them to create a combined screenshot
would add friction and create a new source of errors.

The current design uses one label image plus structured application fields. The
tradeoff is that batch upload becomes harder. For a single label, the form is
clear and easy to use. For 300 labels, nobody wants to type all of that
application data by hand.

I still think that is the right core contract for this prototype. It makes the
comparison target explicit, avoids asking the model to infer application values
from another document, and keeps the result easier to audit.

### Batch Upload

The input-format decision made batch upload the next major tradeoff. I initially
considered a spreadsheet where each row had application fields and a file path
linking to the matching label image. I decided against making that the primary
workflow because it is less approachable. A spreadsheet introduces schema errors,
missing columns, file path mistakes, and the extra burden of matching uploaded
images to text rows. That is powerful, but it is not the most intuitive first
experience for a non-technical reviewer.

If I were extending this product, I would support both workflows: a simple guided
form for manual review, and a spreadsheet-based batch path with a better mapping
step between rows and selected files. I did not build the full spreadsheet path
because I wanted to avoid complicating the prototype with extra controls and
branching workflows. The current flow is intentionally consolidated: select label
images, enter the required application details, verify, and inspect the result.

### Model Choice

I knew the extraction and comparison step would use a vision-capable LLM. This is
the part of the problem where a model is useful: reading imperfect label artwork,
extracting visible text, comparing it to structured application values, and
returning evidence for the reviewer.

I chose OpenRouter for the hosted path because it gives the backend one API
surface for multiple vision-capable models. That makes it easier to switch
models, configure fallbacks, and avoid baking one provider directly into the
product design. For this prototype, that mattered more than optimizing around a
single vendor-specific SDK.

Local execution was the harder tradeoff. I wanted the app to be runnable without
an OpenRouter key, so I added a local provider path through Ollama. The downside
is that local verification is slower and less accurate, depending heavily on the
machine and model. I am comfortable with that tradeoff because local mode is
mainly for demonstration. The deployed path can optimize for both
speed and quality by using stronger hosted models.

## Label Requirements

Sources and more detail about label and application requirements are described
in [docs/assumptions.md](docs/assumptions.md).

- Brand name
- Beverage class and class/type designation
- Alcohol content when required by beverage class and trigger fields
- Net contents
- Name and address of producer, bottler, importer, or similar responsible party
- Country of origin for imported products
- Malt beverage color additive disclosure when applicable
- Government Health Warning Statement as a strict label-only check

## Design And Proposal

The design docs are split by purpose:

- [docs/proposal.md](docs/proposal.md) explains the product goals, invariants,
  architecture posture, security assumptions, and what the prototype is trying
  to prove.
- [docs/design.md](docs/design.md) describes runtime behavior: request flow, UI
  behavior, batch processing, model-provider strategy, failover expectations, and
  Azure-style deployment mechanics.
- [docs/assumptions.md](docs/assumptions.md) captures the working assumptions
  for verification logic.

## Running Locally

Use [docs/startup.md](docs/startup.md) for the full local startup guide. If you
run the setup with Ollama, verification will be slower than in the deployed
environment.
