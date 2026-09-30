import {defineField, defineType} from 'sanity'

// Hierarchical scope: `parent` makes containment data (e.g. enterprise inside all).
export const scope = defineType({
  name: 'scope',
  title: 'Scope',
  type: 'document',
  fields: [
    defineField({name: 'scopeId', title: 'Scope ID', type: 'string', validation: (rule) => rule.required()}),
    defineField({name: 'parent', title: 'Parent scope', type: 'reference', to: [{type: 'scope'}]}),
  ],
})
