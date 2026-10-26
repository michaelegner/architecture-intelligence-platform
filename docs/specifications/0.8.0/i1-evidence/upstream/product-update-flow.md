# Product Update Flow

This flow shows how a product change reliably reaches the storefront without coupling read traffic
to the Catalog Service. The Catalog Service stores both the product change and its event in one
MongoDB transaction; the transactional outbox then publishes the event for independent consumers.

```mermaid
sequenceDiagram
    autonumber
    actor Merchant as Store owner
    participant Admin as Admin Portal
    participant Catalog as Catalog Service<br/>(write side)
    participant CatalogDB as MongoDB<br/>catalog + outbox
    participant Events as Redpanda
    participant Image as Image Service
    participant ProductQuery as Product Query Service
    participant ProductDB as MongoDB<br/>product read model
    participant Storefront as Storefront

    Merchant->>Admin: Edit product details or selected image
    Admin->>Catalog: UpdateProduct (Connect-RPC)
    Catalog->>CatalogDB: Commit product state + event to outbox
    Catalog-->>Admin: Product updated

    Catalog->>Events: Publish ProductUpdated event

    par Update product read model
        Events->>ProductQuery: Consume ProductUpdated event
        ProductQuery->>ProductDB: Upsert versioned product projection
    and Promote selected image when supplied
        Events->>Image: Consume ProductUpdated event
        Image->>Image: Promote draft image for product
        Image->>Events: Publish ProductImagePromoted event
        Events->>ProductQuery: Consume image promotion event
        ProductQuery->>ProductDB: Update image delivery URLs
    end

    Storefront->>ProductQuery: GetProduct / ListProducts
    ProductQuery->>ProductDB: Query optimized read model
    ProductQuery-->>Storefront: Product data with current image URLs
```

**Reliability:** The transactional outbox prevents a database update from being committed without
its corresponding domain event. Projection handlers use event versions, so delayed or out-of-order
messages do not overwrite newer storefront data.

**Trade-off:** The storefront is eventually consistent after a write. In return, read models remain
independent, fast, and horizontally scalable.
