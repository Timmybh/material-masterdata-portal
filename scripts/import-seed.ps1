$pod = kubectl get pods -l app=masterdata-backend -o jsonpath='{.items[0].metadata.name}'
kubectl cp './data/Danh muc vat tu.xlsx' "${pod}:/tmp/items.xlsx"
kubectl exec $pod -- python import_items.py /tmp/items.xlsx
