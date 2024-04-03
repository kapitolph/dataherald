import { Button } from '@/components/ui/button'
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { SheetFooter, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Textarea } from '@/components/ui/textarea'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { toast } from '@/components/ui/use-toast'
import { cn, copyToClipboard, renderIcon } from '@/lib/utils'
import { TableResource } from '@/models/domain'
import { yupResolver } from '@hookform/resolvers/yup'
import { Copy, Loader, Lock, LucideIcon, Unlock } from 'lucide-react'
import { FC, useState } from 'react'
import { useForm } from 'react-hook-form'
import * as Yup from 'yup'

const TABLE_DESCRIPTION_MAX_LENGTH = 500

const formSchema = Yup.object({
  description: Yup.string().max(
    TABLE_DESCRIPTION_MAX_LENGTH,
    `Maximum ${TABLE_DESCRIPTION_MAX_LENGTH} characters are allowed`,
  ),
})
interface TableResourceComponentProps {
  resource: TableResource
  onCancel: () => void
  onSave: (newDescription: string) => Promise<void>
}

const TableResourceComponent: FC<TableResourceComponentProps> = ({
  resource,
  onCancel,
  onSave,
}) => {
  const { id, icon, name } = resource

  const [isSaving, setIsSaving] = useState(false)
  const [editEnabled, setEditEnabled] = useState(!resource.description)

  const form = useForm<{ description?: string }>({
    resolver: yupResolver(formSchema),
    defaultValues: {
      description: resource?.description || '',
    },
  })

  const handleSave = async (data: { description?: string }) => {
    setIsSaving(true)
    await onSave(data.description || '')
    setIsSaving(false)
  }

  const handleCopyId = async () => {
    try {
      await copyToClipboard(id)
      toast({
        variant: 'success',
        title: 'Database ID copied!',
      })
    } catch (error) {
      console.error('Could not copy text: ', error)
      toast({
        variant: 'destructive',
        title: 'Could not copy the Database ID',
      })
    }
  }

  const EditIcon: LucideIcon = editEnabled ? Unlock : Lock

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(handleSave)}
        className="space-y-6 grow flex flex-col"
      >
        <SheetHeader>
          <SheetTitle className="flex items-start gap-1">
            <div>
              {renderIcon(icon, {
                size: 45,
                strokeWidth: 1,
              })}
            </div>
            <div className="flex flex-col">
              <div className="break-all">{name}</div>
              <div className="flex items-center gap-2 text-slate-500 text-xs">
                ID {id}{' '}
                <Button
                  type="button"
                  variant="icon"
                  onClick={handleCopyId}
                  className="p-0 h-fit text-slate-500"
                >
                  <Copy size={12} strokeWidth={2.5} />
                </Button>
              </div>
            </div>
          </SheetTitle>
        </SheetHeader>
        <div className="grow flex flex-col gap-1">
          <div className="flex items-center justify-between gap-2">
            <FormLabel>Table description</FormLabel>
            <TooltipProvider>
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <Button
                    variant="icon"
                    type="button"
                    className="p-0 h-fit"
                    onClick={() => setEditEnabled(!editEnabled)}
                  >
                    <EditIcon size={16} strokeWidth={2.5} />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <strong>Enable</strong> or <strong>disable</strong> editing
                  the table description.
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
          <FormDescription className="mb-1">
            Text descriptions help instruct the AI on how to use a specific
            table.
          </FormDescription>
          <FormField
            control={form.control}
            name="description"
            render={({ field }) => (
              <FormItem className="grow">
                <FormControl>
                  <Textarea
                    className={cn(
                      'resize-none',
                      editEnabled ? 'bg-inherit' : 'bg-gray-100',
                    )}
                    rows={10}
                    {...field}
                    disabled={!editEnabled}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>
        <SheetFooter className="w-full flex sm:justify-between">
          <Button variant="ghost" type="button" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="submit" disabled={isSaving}>
            {isSaving ? (
              <>
                <Loader
                  className="mr-2 animate-spin"
                  size={20}
                  strokeWidth={2.5}
                />{' '}
                Saving
              </>
            ) : (
              'Save'
            )}
          </Button>
        </SheetFooter>
      </form>
    </Form>
  )
}

export default TableResourceComponent
