# Task: list a shop catalog on a new marketplace

## Orientation

Sokol111 is an open-source sample of a multi-tenant online shop. Each merchant is a tenant with its own catalog. Merchants manage products in the shop: name, description, price, available quantity, category, attributes and images. A merchant can disable a product or delete it. Shoppers see the products of a merchant's shop.

The shop is made of independently maintained services. You have their source code and published API repositories at fixed revisions, two architecture documents, authored declarations of the services and the topics they produce, a mapping of broker consumer groups to services, one capture of the broker's consumer groups, and an event catalog generated from the architecture documents. Some service roles also state what they offer or accept in short Promise Contracts. These contracts are fictional. They were written for this exercise and are not statements by the real Sokol111 maintainers. A separate fictional contract describes how the external marketplace processes listing withdrawals.

The new marketplace connection does not exist yet. Orders, checkout and fulfillment are out of scope.

## Task

> A merchant wants to reuse the product catalog from its existing online shop to maintain listings on a new marketplace. Product information, price, availability and images should stay aligned. **The merchant requires the external listing to be withdrawn within 15 minutes when a shop product is disabled or deleted.** Investigate the promises offered by the existing modeled services and what a new consumer may legitimately rely on. Determine **whether any credible set of commitments can satisfy the requirement, which parties would need to make them, and what remains uncertain**. Do not assume the new connector must or can promise the 15-minute outcome. Recommend **proceed / conditional proceed / defer** and explain any proposed commitments or agreements as your conclusion.

## Your answer

Write down:

1. Your first impression: a provisional recommendation in one or two sentences. Write it **before** you open any contract, source file or tool, and do not change it later.
2. Your findings. For each finding, cite its source (a Promise Contract, a file at its revision, or a tool answer).
3. Your recommendation, and the commitments or agreements you propose, if any. Name who would make each one and under which conditions.
4. What remains uncertain.
5. Whether your recommendation changed during the investigation, and which finding changed it.
