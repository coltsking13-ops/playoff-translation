#!/usr/bin/env bash
set -u

cd /workspaces/playoff-translation
mkdir -p logs

for y in 2001 2002 2003 2004 2005 2006 2007 2008 2009 2010 2011 2012; do
  echo ""
  echo "=================================================="
  echo "STARTING PRE-2013 ON-COURT YEAR: $y"
  echo "=================================================="
  date

  PYTHONUNBUFFERED=1 python3 -u scripts/build_pre2013_pbpstats_oncourt_all.py "${y}-${y}" 2>&1 | tee -a "logs/build_pre2013_oncourt_${y}.log"

  code=${PIPESTATUS[0]}

  echo ""
  echo "=================================================="
  echo "FINISHED YEAR: $y EXIT CODE: $code"
  echo "=================================================="
  date

  if [ "$code" -ne 0 ]; then
    echo "Stopped because year $y failed. Check logs/build_pre2013_oncourt_${y}.log"
    exit "$code"
  fi

  sleep 10
done

echo "ALL PRE-2013 YEARS FINISHED"
