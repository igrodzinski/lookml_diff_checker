view: view2 {
  dimension: value {
    type: number
    label: "Value"
  }

  dimension: category {
    type: string
    label: "Category"
  }

  measure: total_value {
    type: sum
    sql: "${TABLE}.value * 2";;
  }
}