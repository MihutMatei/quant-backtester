#!/usr/bin/env bash
# Point the security group's SSH rule at wherever you are right now.
#
# Run it after switching networks (home -> university -> tethering). Requires
# the AWS CLI configured locally; it touches nothing on the instance.
#
#   ./deploy/allow-my-ip.sh sg-0123456789abcdef0
#   QUANT_BOT_SG=sg-0123... ./deploy/allow-my-ip.sh
set -euo pipefail

PORT=22
SG="${1:-${QUANT_BOT_SG:-}}"

if [[ -z "$SG" ]]; then
    echo "Usage: $0 <security-group-id>   (or set QUANT_BOT_SG)" >&2
    exit 1
fi
command -v aws >/dev/null || { echo "aws CLI not installed" >&2; exit 1; }

MYIP="$(curl -fsS https://checkip.amazonaws.com | tr -d '[:space:]')"
[[ -n "$MYIP" ]] || { echo "Could not determine your public IP" >&2; exit 1; }
CIDR="$MYIP/32"

# Authorise the new address BEFORE revoking anything. Security group changes
# apply to established connections, so revoking first could cut the session you
# are currently using to fix this.
if aws ec2 authorize-security-group-ingress --group-id "$SG" \
        --protocol tcp --port "$PORT" --cidr "$CIDR" >/dev/null 2>&1; then
    echo "Allowed $CIDR on port $PORT"
else
    echo "$CIDR was already allowed on port $PORT"
fi

# Drop every other port-22 rule. Without this you accumulate a stale café and
# lecture-hall address every time you move - each one a permanently open door.
STALE="$(aws ec2 describe-security-groups --group-ids "$SG" \
    --query "SecurityGroups[0].IpPermissions[?FromPort==\`$PORT\` && ToPort==\`$PORT\`].IpRanges[].CidrIp" \
    --output text 2>/dev/null || true)"

for old in $STALE; do
    [[ "$old" == "$CIDR" ]] && continue
    aws ec2 revoke-security-group-ingress --group-id "$SG" \
        --protocol tcp --port "$PORT" --cidr "$old" >/dev/null
    echo "Revoked stale rule $old"
done

echo
echo "Current SSH rules on $SG:"
aws ec2 describe-security-groups --group-ids "$SG" \
    --query "SecurityGroups[0].IpPermissions[?FromPort==\`$PORT\`].IpRanges[].CidrIp" \
    --output text | tr '\t' '\n' | sed 's/^/  /'
