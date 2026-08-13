$pod = kubectl get pods -l app=masterdata-backend -o jsonpath='{.items[0].metadata.name}'
kubectl cp './data/Danh muc vat tu.csv' "${pod}:/tmp/items.csv"
kubectl exec $pod -- python import_items.py /tmp/items.csv
