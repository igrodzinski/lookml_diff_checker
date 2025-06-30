
view: view3 {
  set: my_set {
    fields: [id, name]
  }

  drill: my_drill {
    label: "Drill into Details"
    url: "/dashboards/123?id={{ id._value }}"
  }

  dimension: id {
    type: number
  }

  dimension: name {
    type: string
  }
}
