
view: view2 {
  dimension: value {
    type: number
    label: "Transaction Value"
  }

  dimension: category {
    type: string
    label: "Product Category"
  }

  measure: total_value {
    type: sum
    sql: "${TABLE}.value";;
    label: "Total Transaction Value"
  }
}
