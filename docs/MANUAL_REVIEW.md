# Functional configuration and personal review

Use only the private lab at http://127.0.0.1:8171 with database `mxt_demo`.
Credentials are generated in `.local/credentials.json`. All people and businesses
in the fixture are fictional. Review these proposed rules against your memory.

The currently prepared native demo already has quotation `S00001` confirmed,
MO `LPRD/MO/00001` created, and both policies evaluated repeatedly without extra
supply. Start at step 7 to review the pending purchase, receipts and production.
The earlier steps explain how to reproduce preparation from clean fixtures.

1. Sign in as `admin`. Check installed apps: Sales, Purchase, Inventory,
   Manufacturing and MXT Manufacturing Reconstruction. In developer mode,
   inspect Settings → Technical → Scheduled Actions. The reconstruction material
   scheduler is initially disabled; use manual evaluation first.
2. Inventory → Configuration → Warehouses: inspect LRAW, LSUP, LPRD and LFIN.
   LPRD's "Resupply From" includes LSUP. Inspect the generated native route:
   LSUP outbound → internal transit → LPRD inbound. This is the actual stock path.
3. Products: inspect LAB-PANEL, LAB-PACK and LAB-CABINET. All are storable. Review
   the Lab Planning fields. Inspect the two vendors' lead times on purchase tabs.
   LAB-CABINET uses Replenish on Order and Manufacture.
4. Manufacturing → Products → Bills of Materials: the cabinet needs two panels
   and one pack per unit. These are fictional requirements. Native BOMs support
   version-correct variant and UoM behavior; do not manually overwrite stock to
   make a demand disappear.
5. Sales → Quotations: open the fixture quotation for Example Workshop Customer.
   Confirm it. Its native procurement must create one MO for three cabinets in
   LPRD. Use the Manufacturing smart button or the Production Board to open it.
   The Components tab should require six panels and three packs.
6. Manufacturing Lab → Material Policies: evaluate both policies. Panel supply
   should total 12 units: six MO demand + four maximum + two safety buffer.
   Supply is from LSUP, so native transit pickings must exist, without a panel
   purchase at LPRD. Packs should request five units: three demand + two maximum
   + one buffer − one already on hand. Inspect the generated draft RFQ.
   Reevaluate immediately: no duplicate supply documents or quantities should appear.
7. Sign in as `lab.buyer`: open the generated pack RFQ. Review lines and click
   Submit Approval. Try confirming before approval: it must fail. Sign in as
   `lab.manager` and Manager Approve. A low-value request becomes Final Approved.
   Sign back in as buyer and confirm; a native receipt must be created.
8. Test the second tier using a **new** RFQ with an amount above the company
   threshold. Submit as buyer, approve as manager, then approve as `lab.final`.
   A requester must not approve their own request, and the final approver must be
   different from both prior actors. Inspect the immutable Lab Approval history.
   Changing price/quantity after submission must fail until Reset Approval.
   Enter a rejection reason and test Reject Request → Reset → resubmit separately.
9. Inventory → Operations → Transfers: validate the LSUP outbound for panels,
   then its LPRD inbound. Validate the purchase receipt for packs. Reserve and
   record actual quantities with native Odoo controls. Stock remains warehouse
   specific; the transit leg must not magically add stock to both warehouses.
10. As `lab.operator`, open the MO. Confirm if still draft, Review Materials,
    then Materials Ready. Without complete reservations, Ready must fail. After
    supply receipt, move to Ready → Start Lab Production → Request Inspection.
    Kanban dragging follows the same server-side graph; skipping to Completed fails.
11. Record the native quantity producing and actual component consumption, then
    enter fictional inspection findings. The operator cannot Pass Inspection.
    As `lab.quality`, request rework and confirm the card returns to In Production.
    Request inspection again and pass. Rejecting instead must block completion.
12. Mark as Done after the authorized pass.
    Odoo should consume six panels/three packs and produce three cabinets. The
    card becomes Completed only after native completion. Check stock moves.
    Quantity/lot/traceability changes after inspection invalidate completion until
    rework and reinspection; a stored fingerprint binds approval to inspected data.
13. To move cabinets to LFIN, create a native internal transfer from LPRD/Stock
    to LFIN/Stock, reserve, enter actual quantity and validate. No automatic
    post-production transfer is claimed in this reconstruction.
14. MO → Print → Lab Manufacturing and Quality Summary. Confirm the PDF contains
    component quantities, locations, workflow, reviewer and actual findings.
    Material Policy → Print → Lab Material Planning Decisions. Native RFQ/PO and
    picking printing remains available in the original Print menus.
15. Manufacturing → Reporting: group native production analysis by product/date
    and inspect actual quantities/durations. Values reflect demonstration records,
    not asserted original performance. Record screenshots only of fictional data.
16. To automate: enable the reconstruction cron after reviewing policies and
    its execution user. The cron runs hourly with that user's company permissions.
    Managed native orderpoints intentionally use a manual trigger; the custom
    cron evaluates them under a per-company lock. Do not change them to Auto.
    The native fallback also sets `max_cron_threads = 0`; enable one cron thread
    in its private config and restart if you want automatic execution there.
17. To configure new products, add a storable variant, seller and native route;
    create a policy for the warehouse. Minimum and maximum are in the product's
    stock UoM; the safety buffer is added to both. A conflicting existing native
    orderpoint is rejected for manual review. Use native Buy, Manufacture or
    Resupply routes according to the actual business process.
18. Review proposed choices: approval threshold and actors, stage transitions,
    rejection/rework rules, safety stock calculation, supplier selection, demand
    horizon, warehouse boundaries and required inspection evidence. Confirm which
    match your former implementation and which need correction before publication.

See VERIFICATION.md for what was actually executed. The pending acceptance items
must remain visible; untested instructions are not evidence of a successful run.
