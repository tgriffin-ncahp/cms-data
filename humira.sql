SELECT 
	'Humira SFY25', 
	printf('%,d',round(SUM("Units Reimbursed"),0)) as units, 
	printf('%,d',SUM("Number of Prescriptions")) as scripts,
	printf('%,d',round(SUM("Total Amount Reimbursed"),0)) as total, 
	printf('%,d',round(SUM("Medicaid Amount Reimbursed"),0)) as medicaid,
	printf('%,d',round(SUM("Non Medicaid Amount Reimbursed"),0)) as other,
	printf('%,d',round(SUM("Total Amount Reimbursed")/SUM("Units Reimbursed"),1)) as unit_cost
FROM sfy25
WHERE state is 'NC'
AND "Product Name" LIKE '%Humira%';


SELECT 
	state, 
	printf('%,d',round(SUM("Units Reimbursed"),0)) as units, 
	printf('%,d',SUM("Number of Prescriptions")) as scripts,
	printf('%,d',round(SUM("Total Amount Reimbursed"),0)) as total, 
	printf('%,d',round(SUM("Medicaid Amount Reimbursed"),0)) as medicaid,
	printf('%,d',round(SUM("Non Medicaid Amount Reimbursed"),0)) as other,
	printf('%,d',round(SUM("Total Amount Reimbursed")/SUM("Units Reimbursed"),1)) as unit_cost
FROM sfy25
WHERE "Product Name" LIKE '%Humira%'
GROUP BY state
ORDER BY unit_cost DESC;


SELECT
	s.*,
	e.adults,
	e.medicaid,
	e.total
FROM
	sfy25 AS s
JOIN 
	sstate_abbrev as sa
	ON e.state = sa.abbrev
JOIN
	enrollment AS e
	ON s.state = sa.abbrev
LIMIT 10;

ALTER TABLE enrollment
ADD COLUMN state_abbrev TEXT;

UPDATE enrollment
SET st = sa.abbrev
FROM state_abbrev AS sa
WHERE enrollment.state = sa.name;


SELECT 
	s.state, 
	printf('%,d',round(SUM(s."Units Reimbursed"),0)) as units, 
	printf('%,d',SUM(s."Number of Prescriptions")) as scripts,
	printf('%,d',round(SUM(s."Total Amount Reimbursed"),0)) as total, 
	printf('%,d',round(SUM(s."Medicaid Amount Reimbursed"),0)) as medicaid,
	printf('%,d',round(SUM(s."Non Medicaid Amount Reimbursed"),0)) as other,
	printf('%,d',round(SUM(s."Total Amount Reimbursed")/SUM(s."Units Reimbursed"),1)) as unit_cost,
	round(SUM(s."Total Amount Reimbursed")/e.adults,2) as per_adult,
	round(SUM(s."Total Amount Reimbursed")/e.total,2) as per_member,
	printf('%,d',total) as total_mambers,
	printf('%,d',adults) as total_adults,
	round((SUM(s."Units Reimbursed")/(e.adults)*1000),1) as util_adults
FROM	sfy25 as s
JOIN	enrollment as e
	ON s.state = e.st
WHERE	s."Product Name" LIKE '%Humira%'
	AND e.expansion IS 'Expanded'
GROUP BY s.state
ORDER BY util_adults DESC;

SELECT
printf('%,d',SUM("Total Amount Reimbursed")) as total, 
CASE 
  WHEN "Product Name" LIKE '%Humira%' THEN 'Humira'
  WHEN "Product Name" LIKE '%Wegovy%' THEN 'Wegovy'
  ELSE 'other'
END drug
FROM sfy25
WHERE state = 'NC'
GROUP BY drug;
