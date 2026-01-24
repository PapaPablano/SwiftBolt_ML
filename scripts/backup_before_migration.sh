#!/bin/bash
# Quick backup verification before migration
# Run this to check your backup status

echo "🔍 Checking Supabase backup status..."
echo ""
echo "📊 Project: cygflaemtmwiwaviclks"
echo "🌐 Dashboard: https://supabase.com/dashboard/project/cygflaemtmwiwaviclks"
echo ""
echo "✅ Quick Checklist:"
echo "   1. Go to: https://supabase.com/dashboard/project/cygflaemtmwiwaviclks/settings/addons"
echo "   2. Verify 'Point in Time Recovery' is enabled (if on Pro plan)"
echo "   3. OR: Export current options_ranks table as backup"
echo ""
echo "💾 Export options_ranks table (optional safety backup):"
echo "   psql 'postgresql://postgres.[PASSWORD]@db.cygflaemtmwiwaviclks.supabase.co:5432/postgres' \\"
echo "        -c \"\\copy (SELECT * FROM options_ranks) TO 'backup_options_ranks_$(date +%Y%m%d).csv' WITH CSV HEADER\""
echo ""
read -p "✅ Backups verified? Press Enter to continue..."
