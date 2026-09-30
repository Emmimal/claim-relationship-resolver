import {defineArrayMember, defineField, defineType} from 'sanity'

// scope, version and effectiveFrom are deliberately NOT required: the degraded-metadata
// batch needs documents with these missing (Rule 4: missing means unknown).
export const claim = defineType({
  name: 'claim',
  title: 'Claim',
  type: 'document',
  fields: [
    defineField({name: 'claimId', type: 'string', validation: (rule) => rule.required()}),
    defineField({name: 'subject', type: 'string', validation: (rule) => rule.required()}),
    defineField({name: 'attribute', type: 'string', validation: (rule) => rule.required()}),
    defineField({name: 'value', type: 'number', validation: (rule) => rule.required()}),
    defineField({name: 'unit', type: 'string'}),
    defineField({name: 'scope', type: 'reference', to: [{type: 'scope'}]}),
    defineField({name: 'version', type: 'string'}),
    defineField({name: 'effectiveFrom', type: 'date'}),
    defineField({
      name: 'supersedes',
      type: 'array',
      of: [
        defineArrayMember({
          type: 'object',
          name: 'supersession',
          fields: [
            defineField({name: 'claim', type: 'reference', to: [{type: 'claim'}]}),
            defineField({name: 'inScope', type: 'reference', to: [{type: 'scope'}]}),
          ],
        }),
      ],
    }),
    defineField({name: 'sourceId', type: 'string'}),
    // Provenance only. The resolver must never use sourceType (Rule 1).
    defineField({name: 'sourceType', type: 'string'}),
  ],
})
