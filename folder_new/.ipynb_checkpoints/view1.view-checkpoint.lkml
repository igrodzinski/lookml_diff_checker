view: view1 {
  dimension: id {
    type: number
    primary_key: yes
    label: "Identifier"
  }

  dimension: name {
    type: string
    label: "Customer Name"
    drill_fields: [id]
  }
}