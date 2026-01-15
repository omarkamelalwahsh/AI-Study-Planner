# AI Study Planner - Verification Script

Write-Host "=== AI Study Planner - Database Verification ===" -ForegroundColor Cyan
Write-Host ""

# Database connection details (update if needed)
$env:PGPASSWORD = "your_password_here"  # Set your actual password
$dbHost = "localhost"
$dbPort = "5432"
$dbName = "ai_study_planner"  # Update with your actual DB name
$dbUser = "postgres"  # Update with your actual DB user

Write-Host "Checking database table counts..." -ForegroundColor Yellow

# Check plans count
$plansQuery = "SELECT COUNT(*) FROM plans;"
Write-Host "`nPlans count:" -ForegroundColor Green
psql -h $dbHost -p $dbPort -U $dbUser -d $dbName -c $plansQuery

# Check plan_weeks count
$weeksQuery = "SELECT COUNT(*) FROM plan_weeks;"
Write-Host "`nPlan weeks count:" -ForegroundColor Green
psql -h $dbHost -p $dbPort -U $dbUser -d $dbName -c $weeksQuery

# Check plan_items count
$itemsQuery = "SELECT COUNT(*) FROM plan_items;"
Write-Host "`nPlan items count:" -ForegroundColor Green
psql -h $dbHost -p $dbPort -U $dbUser -d $dbName -c $itemsQuery

# Check latest plan
$latestPlanQuery = @"
SELECT p.id, p.weeks, p.hours_per_week, p.created_at, sq.raw_query
FROM plans p
LEFT JOIN search_queries sq ON p.query_id = sq.id
ORDER BY p.created_at DESC
LIMIT 5;
"@

Write-Host "`nLatest 5 plans:" -ForegroundColor Green
psql -h $dbHost -p $dbPort -U $dbUser -d $dbName -c $latestPlanQuery

# Verify foreign keys
$fkQuery = @"
SELECT pi.id, pi.course_id, c.title, c.level
FROM plan_items pi
JOIN courses c ON pi.course_id = c.id
LIMIT 10;
"@

Write-Host "`nSample plan items with course details:" -ForegroundColor Green
psql -h $dbHost -p $dbPort -U $dbUser -d $dbName -c $fkQuery

Write-Host "`n=== Verification Complete ===" -ForegroundColor Cyan
