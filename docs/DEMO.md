# Demo Walkthrough (Review III)

Start the server with `python app.py`, log in as `admin`, and follow the flow below. Open the **Inspector** panel at any step to show the SQL that ran.

## 1. Dashboard
Show the live counts: patients, today's visits, free beds, pending bills.

## 2. Patients and appointments
1. Register a new patient (Patients page).
2. Book an appointment for them (Appointments page).
3. Point out validation: try a duplicate phone number and show the constraint error.

## 3. Emergency
1. Register an emergency case with triage level 1.
2. It appears at the top of the waiting queue (sorted by triage, then arrival time).
3. Click **Start** to move it to Under Treatment. This demonstrates the cursor-style queue output.

## 4. Beds
1. Allot a bed to the admitted patient; the bed turns Occupied.
2. Discharge the patient; the bed becomes Cleaning, then click **Mark Free**.

## 5. Pharmacy
1. Add a prescription for the visit; stock drops (trigger).
2. Show the Low Stock alert; restock a medicine.

## 6. Billing
Generate the bill for the discharged visit (consultation + medicines + bed charge), then mark it paid.

## 7. Reports and Audit
Run a few of the 19 reports (e.g. bed occupancy, low stock, top billed patients). Open the Audit Log to show trigger-written entries for the actions above.

## 8. Roles
Log in as `frontdesk`, `triage_nurse`, `clinical_staff` or `billing_staff` (see the output of `scripts/seed_showcase_data.py` for passwords) and show restricted access.

## Likely viva questions
- Which tables are in 3NF and why? (`db/schema.sql`)
- Where are triggers used? (`db/triggers.sql`: stock reduction on prescriptions, audit logging for visits/bills/patients, doctor availability, audit-log tamper protection)
- How is a transaction kept atomic? (`services.py`, `_execute_in_transaction`)
- Why SQLite? It is a single-file, serverless database with full support for constraints and triggers, which keeps the project easy to run and demonstrate.
