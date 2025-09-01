#!/bin/bash

echo "Checking Apple Sign In logs on EC2..."
echo "This will show the actual audience value from Apple tokens"
echo "----------------------------------------"

ssh -o StrictHostKeyChecking=no -i ~/.ssh/skinsense.pem ubuntu@54.172.133.142 << 'EOF'
echo "Recent Apple Sign In attempts:"
docker logs skinsense_backend 2>&1 | grep -i -A 2 -B 2 "apple" | tail -50
echo ""
echo "Looking for audience values:"
docker logs skinsense_backend 2>&1 | grep -i "audience" | tail -10
echo ""
echo "Looking for 'Consider adding' suggestions:"
docker logs skinsense_backend 2>&1 | grep "Consider adding" | tail -5
EOF

echo "----------------------------------------"
echo "If you see 'Consider adding' messages above, those show the exact"
echo "audience value that Apple is sending and needs to be added to the backend."