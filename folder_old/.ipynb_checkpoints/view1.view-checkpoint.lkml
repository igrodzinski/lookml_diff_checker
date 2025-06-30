
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
measure:count{
type:count
}
set: set1{fields:[]}
}
