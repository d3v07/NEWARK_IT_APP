# DMSD FINAL PROJECT


## We built the Newark‐IT application as a classic Flask+MySQL CRUD system, organized into four major modules—Customer Management, Online Sales (Baskets & Orders), Transaction History, and Sales Statistics.

1. Customer Management: A single customers.html template drives list, create, edit and delete flows. New customer IDs are auto‐incremented and we automatically assign each a default shipping label of Home_<CID>. On the customer detail page you can add/edit/delete shipping addresses and credit cards inline; deleting a customer cascades through baskets and orders, while stored cards are nulled out for audit.

2. Online Sales: We maintain a Basket table and an Appears_In join table for basket items. From the basket list you can create a new basket for any customer, adjust quantities or remove items, and then click Place Order. That takes you to a “New Transaction” form which—by filtering on the selected basket’s CID—shows only that customer’s shipping labels and stored cards, plus an inline “add new card” option. On submission we recalculate each line’s PriceSold (applying special offer pricing for gold/platinum customers), insert the Transaction row (with TotalAmount), decrement stock in Product.PQuantity, and redirect to the transaction list.

3. Transaction History: The transactions.html listing supports filtering by customer name, product name, or date range, and includes side-by-side Edit/Delete buttons. Editing lets you swap a shipping label or stored card and toggle delivered/not-delivered; deleting simply removes the row. We added “Customer History” and “Card History” links on the customer and card detail pages, respectively, so you can drill down to see exactly which orders a given customer placed or which baskets used a specific card.

4. Sales Statistics: A lightweight “Statistics” interface runs six parameterized reports—total charged per card, top-10 customers, most-sold products, distinct-customer counts, max-basket totals per card, and average price per category—each over a user-supplied date range.

II.  Problems Faced & Solutions

1. Foreign-Key Cascades & Orphans
Early on we discovered that deleting a customer left orphaned credit-card rows. Switching the Credit_Card.StoredCardCID FK to ON DELETE SET NULL resolved it, but we had to write a one-off cleanup script to scrub existing orphans before deploying the new constraint.

2. Dynamic Pricing Logic
Implementing “gold/platinum offer pricing” in Python against two tables (Offer_Product vs. Product) introduced subtle bugs whenever a product had no active offer. We ultimately refactored into a single loop in the new_transaction route that: fetches the customer’s status, pulls basket items, deletes and re-inserts them with the correct PriceSold, then computes the total.

3. Filtering & Scoped Lookups
The transaction filters originally fetched every shipping label and card in the DB, not scoped to the chosen basket’s customer. We fixed this by passing the selected bid back into the GET parameters and adding WHERE CID = (SELECT CID FROM Basket WHERE BID=…) clauses so that only the relevant addresses/cards appear.

4. Template Layout & Button Alignment
Getting the Edit/Delete buttons to sit neatly side-by-side took several rounds of tweaking inline CSS (display:flex; gap:…) and switching from <a>+<button> to a unified flex container with margin resets.

5. Race Conditions on Stock Updates
In high-concurrency scenarios, two users placing orders on the same product could oversell. We addressed this by wrapping the stock-decrement UPDATE in the same transaction as the inserts and committing at the end, which at least guarantees atomicity; a future improvement would be explicit row-locking or SELECT … FOR UPDATE.

6. Rollback & Reversibility
Because you asked to be able to revert features, we kept all new routes and template fragments isolated—nothing overwrote core routes—and documented every change so you can drop or rename the added endpoints without touching the original project.
