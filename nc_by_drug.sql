UPDATE sfy24
SET product =
  CASE
    WHEN instr("Product Name", ' ') > 0
      THEN substr("Product Name", 1, instr("Product Name", ' ') - 1)
    ELSE "Product Name"
  END;

SELECT 
s.product, 
sum(s.'Number of Prescriptions') as rx_total, 
SUM(s.'Units Reimbursed') as units, 
SUM(s.'Total Amount Reimbursed') as total_amount 
FROM sfy24 as s
JOIN ndc26 AS n
ON n.product = s.product
GROUP BY s.'Product Name'
ORDER BY s.'Product Name';
