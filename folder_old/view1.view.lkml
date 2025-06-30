
view: view1 {
  dimension: id {
    type: number
    primary_key: yes
    label: "Identifier"
  }

  dimension: name {
    type: string
    label: "Name"
  }

  dimension: new_dimension {
    type: string
    sql: "${TABLE}.new_column";;
  }

  dimension_group: business_date {
    type: time
    timeframes: [date, week, month]
sql: "${TABLE}.business_date";;
  }
}