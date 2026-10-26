# Store Lifecycle

The platform supports a clear lifecycle: create a store, manage its catalog, then serve shoppers
through fast read models.

```mermaid
flowchart TB
    classDef actor fill:#eef2ff,color:#312e81,stroke:#818cf8,stroke-width:2px
    classDef ui fill:#ecfeff,color:#155e75,stroke:#22d3ee,stroke-width:2px
    classDef service fill:#eff6ff,color:#1e3a8a,stroke:#60a5fa,stroke-width:2px
    classDef event fill:#fff7ed,color:#9a3412,stroke:#fb923c,stroke-width:2px
    classDef query fill:#faf5ff,color:#6b21a8,stroke:#c084fc,stroke-width:2px
    classDef data fill:#f8fafc,color:#334155,stroke:#94a3b8,stroke-width:2px

    platformOperator[Platform operator]:::actor
    merchant[Store owner]:::actor
    shopper[Shopper]:::actor

    platformOperator ~~~ merchant
    merchant ~~~ shopper

    subgraph launch[1. Launch a store]
        direction TB
        platformPortal[Platform Portal<br/>platform.sokolshop.com]:::ui
        tenant[Tenant Service<br/>provisions an isolated tenant]:::service
        platformPortal -->|create store| tenant
    end

    subgraph operate[2. Manage products]
        direction TB
        admin[Admin Portal<br/>admin.sokolshop.com]:::ui
        catalog[Catalog Service<br/>products, categories, attributes]:::service
        images[Image Service<br/>product media]:::service
        admin -->|manage catalog| catalog
        admin -->|upload images| images
    end

    subgraph shop[3. Shop]
        direction TB
        broker[Redpanda<br/>domain event bus]:::event
        readModels[Product and Category<br/>Query Services]:::query
        storefront[Storefront<br/>your-store.sokolshop.com]:::ui
        broker -->|build projections| readModels -->|fast reads| storefront
    end

    platformOperator --> platformPortal
    merchant --> admin
    shopper --> storefront

    tenant -. TenantUpdated event .-> broker
    catalog -. Product and category events .-> broker
    images -. ProductImagePromoted event .-> broker

    subgraph foundation[Shared platform foundation]
        direction LR
        database[(MongoDB<br/>database per tenant)]:::data
        storage[(Object storage<br/>and imgproxy)]:::data
        identity[Logto<br/>authentication]:::data
    end

    tenant --- database
    catalog --- database
    readModels --- database
    images --- storage
    platformPortal -.- identity
    admin -.- identity
    storefront -.- identity
```

**Tenant isolation:** A tenant is provisioned once and its context travels with every request.
Tenant data is stored in a dedicated MongoDB database, while the platform remains a shared SaaS
deployment.

**Fast storefronts:** Catalog changes are published as events and projected into dedicated query
services. Shoppers read from those optimized models rather than from the write service.
