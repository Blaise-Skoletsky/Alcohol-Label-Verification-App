# Alcohol Label Verification App

## Introduction

This is my submission for the Treasury take-home test.

The application is a prototype for checking alcohol label artwork against
structured application data. It is not meant to be a final legal approval system.
The goal is to show the product approach: what inputs I chose, what I decided not
to support, and how I balanced speed, accuracy, and usability.

## Tradeoffs

The main tension during development was balancing two things:

- Speed and accuracy.
- A simple UI/UX while still keeping the workflow powerful enough for real review
  work.

The first major design decision was the input format. When I started, I was
scraping the COLA site for labels and applications. In those scraped examples,
the label and application often appeared together in one combined image. My first
idea was to let users upload that single combined image and have the model pull
out both the application text and the label text, then compare the two.

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

That led to the second design decision: whether to support spreadsheet upload. I
initially considered a spreadsheet where each row had application fields and a
file path linking to the matching label image. I decided against making that the
primary workflow because it is less approachable. A spreadsheet introduces schema
errors, missing columns, file path mistakes, and the extra burden of matching
uploaded images to text rows. That is powerful, but it is not the most intuitive
first experience for a non-technical reviewer.

If I were extending this product, I would support both workflows: a simple guided
form for manual review, and a spreadsheet-based batch path with a better mapping
step between rows and selected files. I did not build the full spreadsheet path
because I wanted to avoid complicating the prototype with extra controls and
branching workflows. The current flow is intentionally consolidated: select label
images, enter the required application details, verify, and inspect the result.

The third major decision was model execution. I knew the extraction and
comparison step would use a vision-capable LLM. For a hosted environment, current
vision LLM's are cheap, fast and accurate. 

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
